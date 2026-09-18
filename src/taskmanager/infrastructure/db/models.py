"""The three ORM row classes: the persistence shape of the three entities.

They are separate classes from `domain.entities.*` on purpose (DB-03). The
rejected alternative is an imperative mapping of the dataclasses themselves,
which reads as less code but fuses the entity with its storage: the entity would
then carry SQLAlchemy instrumentation, an expired attribute could emit SQL from
inside a use case, and the "domain imports nothing" claim
`tests/architecture/test_domain_is_stdlib_only.py` proves would stop being
interesting. Explicit mappers pay a few lines per aggregate to keep that apart.

Neither the enums nor the timestamps are delegated to the database (D-11).
`status` and `priority` are `VARCHAR` with named `CHECK` constraints rather than
PostgreSQL `ENUM` types, because adding a member to a PostgreSQL enum is a
migration that cannot run inside a transaction on older servers and cannot be
reversed at all; a `CHECK` list is an ordinary `ALTER TABLE`. No column below
delegates its value to a server-side default either - the `Clock` port is the
only source of time (Phase 2 D-13/D-14), and a value the ORM did not put there
would also show up as permanent `alembic check` drift. The keyword that would
express it is deliberately absent from this file, so the plan's grep gate can
stay strict; `tests/unit/infrastructure/test_models.py` proves the absence.

**Corrected reading of D-10.** D-10 lists `users` without `updated_at` and
`task_lists` without `description`, but both fields exist on the entities
(`user.py` L42, `task_list.py` L44) and a mapper cannot round-trip a field that
has no column. Both are therefore part of the baseline, as a correction made
here rather than as a second migration invented later to patch it.
"""

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taskmanager.infrastructure.db.base import Base
from taskmanager.infrastructure.db.constraints import UQ_USERS_EMAIL_LOWER


class UserRow(Base):
    """A row of `users`, mirroring `domain.entities.user.User`."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # The one name the convention cannot generate: an expression index has
        # no `column_0_N_name` to interpolate, so it is read from the constants
        # module instead of being typed here a second time.
        Index(UQ_USERS_EMAIL_LOWER, text("lower(email)"), unique=True),
    )


class TaskListRow(Base):
    """A row of `task_lists`, mirroring `domain.entities.task_list.TaskList`."""

    __tablename__ = "task_lists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    # `lazy="raise"` turns an accidental lazy load into an InvalidRequestError
    # the moment a developer writes it, instead of a MissingGreenlet raised from
    # async code at runtime in front of a user (DB-03, roadmap SC-2). Every
    # query that genuinely needs the children asks for them with selectinload().
    # `passive_deletes=True` leaves DB-05's ON DELETE CASCADE to PostgreSQL:
    # without it SQLAlchemy would try to load the children it just refused to
    # load, in order to null out a column the database is about to delete.
    tasks: Mapped[list["TaskRow"]] = relationship(lazy="raise", passive_deletes=True)

    __table_args__ = (
        # Unnamed on purpose: the `uq` convention renders exactly D-12's
        # `uq_task_lists_owner_id_name`. It is case-SENSITIVE - plain
        # `UNIQUE (owner_id, name)`, never `lower(name)` - which is the
        # deliberate opposite of `uq_users_email_lower` above. `User` lowercases
        # its address on construction, so that index only defends a rule the
        # entity already enforces; `TaskList` folds no case at all, so a
        # case-insensitive index here would refuse two names the entity
        # considers distinct (D-12).
        UniqueConstraint("owner_id", "name"),
        # Deliberately absent: an index on `owner_id` alone. It is the leading
        # column of the unique constraint above, and PostgreSQL serves a
        # leading-column lookup from that index already.
    )


class TaskRow(Base):
    """A row of `tasks`, mirroring `domain.entities.task.Task`."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    task_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("task_lists.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    due_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        # `name=` supplies only the `%(constraint_name)s` half of the `ck`
        # convention, which prefixes the table: `name="status"` -> ck_tasks_status.
        CheckConstraint(
            "status IN ('pending','in_progress','completed')", name="status"
        ),
        CheckConstraint("priority IN ('low','medium','high')", name="priority"),
        # The database copy of the entity invariant at `task.py` L83-87
        # (Phase 2 review fix WR-07): completed_at is set exactly when the task
        # is completed, in both directions.
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="completed_at_matches_status",
        ),
        # Deliberately absent: a composite (task_list_id, status, priority)
        # index. `ix_tasks_task_list_id`, declared on the column above, already
        # narrows every Phase 4 query to one list's rows before the status or
        # priority filter applies; a wider index would be speculation until a
        # real plan shows it is needed.
    )
