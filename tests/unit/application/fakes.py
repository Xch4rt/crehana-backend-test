"""In-memory test doubles for the eight application ports.

They live under `tests/` on purpose. A fake under `src/` would be shipped code
with no caller, and it would drag the ports into the coverage report as
*implemented* rather than declared - which is precisely the claim ARC-04 and
roadmap success criterion 3 make about them. Here they are test material:
outside `coverage`'s source, outside import-linter's graph, and unreachable
from the production application.

They are also the reason the application layer is cheap to cover. Every use case
is pure orchestration over these ports, so a full happy path plus every failure
branch runs in microseconds against dictionaries, with no database, no event
loop tuning and no fixtures beyond a constructor call. Phase 3 writes the real
SQLAlchemy adapters against the same Protocols; nothing here is replaced by
them, because nothing here was ever the implementation.
"""

from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from taskmanager.application.ports.repositories import (
    TaskListRepository,
    TaskRepository,
    UserRepository,
)
from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.domain.exceptions import EmailAlreadyRegisteredError
from taskmanager.domain.value_objects.completion import CompletionStats
from taskmanager.domain.value_objects.task_priority import TaskPriority
from taskmanager.domain.value_objects.task_status import TaskStatus


class FakeTaskRepository:
    """Tasks in a dict, plus a record of every mutation that was asked for.

    `added`, `updated` and `deleted` exist so a use-case test can assert that a
    write happened *exactly once*. Asserting only on the final stored state
    would pass just as happily if the use case saved twice.

    `held_for_update` is the same idea for ADR-058. A dictionary has no second
    writer to keep out, so this fake cannot model the waiting - the
    two-connection suite in `tests/integration/test_concurrent_writes.py` is
    where that is proved. What it can do is record *which road a use case took*:
    a write path that loaded through `get` leaves this list empty, and a read
    path that loaded through `get_for_update` fills it, and both are failing
    assertions in the use-case suites.
    """

    def __init__(self) -> None:
        self.stored: dict[UUID, Task] = {}
        self.added: list[Task] = []
        self.updated: list[Task] = []
        self.deleted: list[UUID] = []
        self.held_for_update: list[UUID] = []

    async def get(self, task_id: UUID) -> Task | None:
        return self.stored.get(task_id)

    async def get_for_update(self, task_id: UUID) -> Task | None:
        self.held_for_update.append(task_id)
        return self.stored.get(task_id)

    async def add(self, task: Task) -> None:
        self.stored[task.id] = task
        self.added.append(task)

    async def update(self, task: Task) -> None:
        self.stored[task.id] = task
        self.updated.append(task)

    async def delete(self, task_id: UUID) -> None:
        self.stored.pop(task_id, None)
        self.deleted.append(task_id)

    async def list_for_task_list(
        self,
        task_list_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> Sequence[Task]:
        tasks = [
            task for task in self.stored.values() if task.task_list_id == task_list_id
        ]
        if status is not None:
            tasks = [task for task in tasks if task.status is status]
        if priority is not None:
            tasks = [task for task in tasks if task.priority is priority]
        # Ordered by `(created_at, id)`, exactly as the SQLAlchemy adapter's
        # `ORDER BY` is, and for the reason `list_for_owner` below gives at
        # length: the fake used to return insertion order, which is a divergence
        # with teeth - a D-13 assertion about the first element would pass here
        # and fail over HTTP, where PostgreSQL is free to answer in whatever
        # order the plan produced. `created_at` alone is not a total order
        # either, since the clock is read once per request.
        return sorted(tasks, key=lambda entry: (entry.created_at, entry.id))

    async def list_for_assignee(self, assignee_id: UUID) -> Sequence[Task]:
        # D-02's discovery query: assignee only, across every list, and sorted
        # on `(created_at, id)` for the reason spelled out just above - the
        # adapter's `ORDER BY` says the same thing, and a fake that answered in
        # insertion order would make an ordering assertion pass here and fail
        # over HTTP.
        assigned = [
            task for task in self.stored.values() if task.assignee_id == assignee_id
        ]
        return sorted(assigned, key=lambda entry: (entry.created_at, entry.id))

    async def completion_stats(self, task_list_id: UUID) -> CompletionStats:
        # Counted from what is stored, not canned: the aggregate Phase 3 will
        # write in SQL has to agree with this, so the fake must be able to
        # disagree with a wrong use case.
        tasks = [
            task for task in self.stored.values() if task.task_list_id == task_list_id
        ]
        completed = [task for task in tasks if task.status is TaskStatus.COMPLETED]
        return CompletionStats(total=len(tasks), completed=len(completed))


class FakeTaskListRepository:
    """Task lists in a dict, with the same mutation record as its sibling."""

    def __init__(self, tasks: FakeTaskRepository | None = None) -> None:
        # LIST-03's counters are about tasks, and a task-list repository has no
        # tasks of its own. The adapter reaches them through a join; the fake is
        # handed the sibling repository explicitly, and `FakeUnitOfWork` passes
        # the one it already constructs so a use case sees the two agree. The
        # rejected alternative is counting from a canned dict set by the test:
        # that would make every LIST-03 assertion true by construction, which is
        # exactly what `FakeTaskRepository.completion_stats` refuses to do.
        # Defaulted so a test that only needs the list side still builds one.
        self.tasks = tasks if tasks is not None else FakeTaskRepository()
        self.stored: dict[UUID, TaskList] = {}
        self.added: list[TaskList] = []
        self.updated: list[TaskList] = []
        self.deleted: list[UUID] = []
        # See `FakeTaskRepository`: which road a use case took, not the waiting.
        self.held_for_update: list[UUID] = []

    async def get(self, task_list_id: UUID) -> TaskList | None:
        return self.stored.get(task_list_id)

    async def get_for_update(self, task_list_id: UUID) -> TaskList | None:
        self.held_for_update.append(task_list_id)
        return self.stored.get(task_list_id)

    async def add(self, task_list: TaskList) -> None:
        self.stored[task_list.id] = task_list
        self.added.append(task_list)

    async def update(self, task_list: TaskList) -> None:
        self.stored[task_list.id] = task_list
        self.updated.append(task_list)

    async def delete(self, task_list_id: UUID) -> None:
        self.stored.pop(task_list_id, None)
        self.deleted.append(task_list_id)

    async def list_for_owner(self, owner_id: UUID) -> Sequence[TaskList]:
        # Ordered by `(created_at, id)`, exactly as the SQLAlchemy adapter's
        # `ORDER BY` is. The fake used to return insertion order, and that is a
        # divergence with teeth: a D-13 assertion about the first element would
        # pass here and fail over HTTP, where PostgreSQL is free to answer in
        # whatever order the plan produced. `created_at` alone is not a total
        # order either - the clock is read once per request, so two lists made
        # in one call share an instant - hence the `id` tie-break.
        owned = [
            task_list
            for task_list in self.stored.values()
            if task_list.owner_id == owner_id
        ]
        return sorted(owned, key=lambda entry: (entry.created_at, entry.id))

    async def list_for_owner_with_stats(
        self, owner_id: UUID
    ) -> Sequence[tuple[TaskList, CompletionStats]]:
        # Counted from what the task fake has stored, never canned, for the
        # reason `FakeTaskRepository.completion_stats` gives: the fake has to be
        # able to disagree with a wrong use case.
        #
        # The sort is repeated here rather than delegated to `list_for_owner`,
        # and that mirrors the adapter, where `list_for_owner`'s `ORDER BY` and
        # `lists_with_stats_statement`'s are two separate clauses. A delegation
        # would make this method's ordering a consequence of the other one's,
        # so the test below would keep passing if the grouped statement lost its
        # `ORDER BY` entirely.
        owned = [
            (task_list, await self.tasks.completion_stats(task_list.id))
            for task_list in self.stored.values()
            if task_list.owner_id == owner_id
        ]
        return sorted(owned, key=lambda entry: (entry[0].created_at, entry[0].id))

    async def exists_with_name(self, owner_id: UUID, name: str) -> bool:
        # Case-SENSITIVE, matching `uq_task_lists_owner_id_name` - the plain
        # `UNIQUE (owner_id, name)` of D-12, not a case-folding expression index.
        # `TaskList` folds no case on its name, so `Alpha` and `alpha` are two
        # distinct lists and a fake that compared case-insensitively would fail
        # a use case the database would have accepted. The stored value is
        # already trimmed by `require_text`, so only the argument is stripped.
        return any(
            task_list.owner_id == owner_id and task_list.name == name.strip()
            for task_list in self.stored.values()
        )


class FakeUserRepository:
    """Users in a dict, indexed by id, with the login lookup over the values."""

    def __init__(self) -> None:
        self.stored: dict[UUID, User] = {}
        self.added: list[User] = []

    async def get(self, user_id: UUID) -> User | None:
        return self.stored.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        # `User` lowercases on construction, so the stored side is canonical
        # already and only the argument needs folding.
        wanted = email.strip().lower()
        return next(
            (user for user in self.stored.values() if user.email == wanted),
            None,
        )

    async def add(self, user: User) -> None:
        # Refuses a duplicate address exactly as the adapter does, and for the
        # same reason `list_all`'s ordering was brought into line in 05-02:
        # a fake that accepts what the database refuses makes a whole class of
        # use-case behaviour untestable. Until this line existed, `add` stored
        # unconditionally, so `RegisterUser`'s race backstop - the leg CLAUDE.md
        # requires, where the pre-check saw nothing and `uq_users_email_lower`
        # catches it anyway - could not be exercised against the fakes at all.
        # The error takes no argument here either: there is nothing to pass, so
        # no call site can leak the address by being helpful.
        #
        # The comparison is made against `stored` directly rather than through
        # `get_by_email`, and that is the difference between modelling the
        # index and modelling the query: PostgreSQL does not consult a
        # repository method before enforcing a constraint, so a subclass that
        # overrides the lookup - which is exactly how a test reproduces the
        # race - must still be refused here.
        wanted = user.email.strip().lower()
        if any(stored.email == wanted for stored in self.stored.values()):
            raise EmailAlreadyRegisteredError()
        self.stored[user.id] = user
        self.added.append(user)

    async def list_all(self) -> Sequence[User]:
        # Ordered by `(created_at, id)`, exactly as the SQLAlchemy adapter's
        # `ORDER BY` is (D-25). This fake used to return insertion order, and
        # that is a divergence with teeth: an ASGN-03 assertion about the first
        # entry of the directory would pass here and fail over HTTP, where
        # PostgreSQL is free to answer in whatever order the plan produced.
        # `created_at` alone is not a total order either - a seed script or a
        # fixture writes several accounts under one clock reading - which is why
        # the adapter took the `id` tie-break as review fix WR-03.
        #
        # It is the last of the three fakes to be fixed: the sibling list
        # methods were brought into line in 04-02 and 04-06 and this one was
        # missed, so the divergence was falsified before being removed. The
        # failing run is in
        # `.planning/phases/05-auth-assignment-notifications/evidence/
        # 05-02-fake-user-ordering.txt`.
        return sorted(
            self.stored.values(), key=lambda entry: (entry.created_at, entry.id)
        )


class FakeUnitOfWork:
    """The three fake repositories behind one countable transaction boundary.

    `commits` and `rollbacks` are the point of this class. A use case that
    forgets to commit, or commits on a path that raised, is otherwise
    indistinguishable from a correct one when the repositories are dictionaries
    that never had a transaction to begin with. `rollbacks` only measures
    anything because `__aexit__` below honours the port's obligation to roll
    back an uncommitted block: a fake that skipped it would let every failure
    test pass against an adapter that leaks a dirty session back to the pool.

    Each repository is reachable under two names, and that is not redundancy.
    `UnitOfWork` declares `tasks`, `task_lists` and `users` as mutable attributes,
    and mypy checks a mutable protocol member *invariantly* - so the attribute
    the use case sees has to be annotated with the port type exactly, or this
    class stops satisfying the port at all. The `*_repository` aliases beside
    them are the very same objects under their concrete type, and they are what
    a test asserts on when it needs `added`, `updated`, `deleted` or `stored`.
    """

    def __init__(
        self,
        tasks: FakeTaskRepository | None = None,
        task_lists: FakeTaskListRepository | None = None,
        users: FakeUserRepository | None = None,
    ) -> None:
        self.task_repository = tasks if tasks is not None else FakeTaskRepository()
        # The list repository is given the very task repository this unit of
        # work exposes, so `list_for_owner_with_stats` counts the same tasks a
        # use case added through `uow.tasks`. A caller that supplies its own
        # `task_lists` fake has already made that wiring decision itself.
        self.task_list_repository = (
            task_lists
            if task_lists is not None
            else FakeTaskListRepository(self.task_repository)
        )
        self.user_repository = users if users is not None else FakeUserRepository()
        self.tasks: TaskRepository = self.task_repository
        self.task_lists: TaskListRepository = self.task_list_repository
        self.users: UserRepository = self.user_repository
        self.commits = 0
        self.rollbacks = 0
        self._finished = False

    async def __aenter__(self) -> Self:
        self._finished = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # The port makes this method responsible for rolling back whatever was
        # not committed, on every exit path, so the fake models exactly that.
        # Leaving `rollbacks` as a counter nothing ever incremented is what let
        # the whole suite stay green against a use case - or a Phase 3 adapter -
        # that never returns its session clean: `commits == 0` proves nothing
        # was written, never that the transaction was actually closed.
        if not self._finished:
            self.rollbacks += 1
        self._finished = False
        # Two deliberate non-behaviours, both load-bearing. Returning `None`
        # rather than a true value means an exception leaving the block is
        # never swallowed, so a failing use case cannot answer 200. And no
        # automatic commit happens here: D-17 and ARC-08 put the commit in the
        # use case, explicitly, which is what the `commits` counter measures.
        return None

    async def commit(self) -> None:
        self.commits += 1
        self._finished = True

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._finished = True


class FrozenClock:
    """A clock stopped at one instant, which it returns for ever.

    The domain never reads a clock (D-13): every entity method takes `now` as a
    keyword argument, and the use case is the one component that calls this
    port. So a frozen instant is all a test needs to make every `updated_at` and
    `completed_at` assertion an exact equality rather than a tolerance.
    """

    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


class FakePasswordHasher:
    """A reversible prefix in place of Argon2id: deterministic and instant.

    Real hashing is intentionally expensive, which is a property no unit test
    wants to pay for on every run. The prefix keeps `verify` honest - a wrong
    password still fails - without any of the cost.

    `dummy_verifications` is the recorder for D-21's `dummy_verify`. The real
    method exists to make the unknown-email leg of a login cost the same as the
    wrong-password leg, and a test that tried to prove that by reading a clock
    would be measuring a machine rather than a decision - so the fake records
    that the work was *requested*, and plan 05-07's `Login` tests assert on the
    list instead.

    `hashed` and `verifications` are the same idea for the other two methods.
    T-5-07 says an over-long password must never reach Argon2 at all, and the
    only honest way to assert that in a unit suite is to ask the hasher whether
    it was called - `RegisterUser`'s policy test reads `hashed`, and `Login`'s
    two refusal legs read `verifications` against `dummy_verifications` to show
    that each leg paid the work the other one paid.
    """

    PREFIX = "fake-hash:"

    def __init__(self) -> None:
        self.hashed: list[str] = []
        self.verifications: list[tuple[str, str]] = []
        self.dummy_verifications: list[str] = []

    async def hash(self, password: str) -> str:
        self.hashed.append(password)
        return f"{self.PREFIX}{password}"

    async def verify(self, password: str, hashed: str) -> bool:
        self.verifications.append((password, hashed))
        return hashed == f"{self.PREFIX}{password}"

    async def dummy_verify(self, password: str) -> None:
        # Nothing expensive and nothing returned, exactly as the port declares:
        # the cost being equalised belongs to Argon2id, which this class exists
        # to avoid paying. Recording the call is the whole behaviour.
        self.dummy_verifications.append(password)


class FakeTokenService:
    """A token that is the stringified subject, so decoding is inspectable."""

    async def issue_access_token(self, subject: UUID) -> str:
        return str(subject)

    async def decode(self, token: str) -> UUID:
        return UUID(token)


class FakeEmailNotifier:
    """Records what would have been sent, so a test can assert on it."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, UUID]] = []

    async def send_task_assigned(
        self,
        *,
        recipient_email: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        self.sent.append((recipient_email, task_title, task_id))
