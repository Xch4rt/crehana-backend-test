"""What the schema promises, proven against compiled DDL and no database.

DB-03, DB-04, DB-05, D-11 and D-12 are all statements about the *shape* of three
tables, and SQLAlchemy can render that shape for the PostgreSQL dialect without
a connection. The rejected alternative is asserting the same things from an
integration test: it would be slower, it would only run where PostgreSQL is
reachable, and - worse - it would conflate "the model says CASCADE" with "the
migration was applied". Plan 03-05 owns the second question against a real
server; this file owns the first, and it is the one that fails within a second
of a wrong `ondelete=`.

The constraint names are not spelled out here either. They are read back from
`infrastructure.db.constraints`, so a constant added there without a
corresponding object in the schema fails this file rather than waiting for D-13's
error translation to silently stop matching.
"""

from typing import Final

from sqlalchemy import Column, DateTime, String, Table, create_engine
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from taskmanager.domain.entities.task import Task
from taskmanager.domain.entities.task_list import TaskList
from taskmanager.domain.entities.user import User
from taskmanager.infrastructure.db import constraints
from taskmanager.infrastructure.db.base import Base
from taskmanager.infrastructure.db.models import TaskListRow, TaskRow, UserRow

TABLE_NAMES: Final[tuple[str, ...]] = ("users", "task_lists", "tasks")

# The dialect the application actually runs on, obtained without a connection:
# `create_engine` resolves the dialect and the DBAPI eagerly but connects
# lazily, so nothing here needs PostgreSQL to be reachable. The shorter
# `postgresql.dialect()` is rejected for one reason only - it is an unannotated
# call, and mypy strict refuses it in a typed context (`no-untyped-call`).
DIALECT: Final[Dialect] = create_engine("postgresql+psycopg://").dialect

# The rendered form of a case-insensitive expression index: required on the
# users email, refused on the task-list name (D-12).
CASE_FOLDED_INDEX: Final[str] = "lower(%s)"

# Every `Final` name in the constants module, read back rather than retyped.
D12_CONSTRAINT_NAMES: Final[frozenset[str]] = frozenset(
    value
    for name, value in vars(constraints).items()
    if name.isupper() and isinstance(value, str)
)


def _table(name: str) -> Table:
    """The mapped `Table` for one of the three row classes."""
    return Base.metadata.tables[name]


def _tables() -> list[Table]:
    """The three tables, in dependency order."""
    return [_table(name) for name in TABLE_NAMES]


def _ddl(table: Table) -> str:
    """The PostgreSQL DDL for one table, including its indexes."""
    statements = [str(CreateTable(table).compile(dialect=DIALECT))]
    statements.extend(
        str(CreateIndex(index).compile(dialect=DIALECT)) for index in table.indexes
    )
    return "\n".join(statements)


def _schema_ddl() -> str:
    """The DDL of the whole schema: three tables and every index on them."""
    return "\n".join(_ddl(table) for table in _tables())


def _columns(table: Table) -> list[Column[object]]:
    """Every column of one table, as a list so it can be counted."""
    return list(table.columns)


def _string_length(table_name: str, column_name: str) -> int | None:
    """The declared `String(n)` cap of one column."""
    column_type = _table(table_name).columns[column_name].type
    assert isinstance(column_type, String)
    return column_type.length


def test_the_naming_convention_produces_every_d12_constraint_name() -> None:
    """Every name D-13 will key its error translation on exists in the schema.

    The expected set is derived from the constants module, so adding a constant
    without giving it a home in the schema turns this test red - which is the
    only moment the mismatch is cheap to fix.
    """
    ddl = _schema_ddl()

    # Vacuity guard: an empty constant set would make the loop below assert
    # nothing at all.
    assert len(D12_CONSTRAINT_NAMES) == 12

    missing = sorted(name for name in D12_CONSTRAINT_NAMES if name not in ddl)

    assert missing == []


def test_the_task_list_name_unique_constraint_is_case_sensitive() -> None:
    """`uq_task_lists_owner_id_name` is plain `UNIQUE (owner_id, name)` (D-12).

    `Alpha` and `alpha` are two different lists for the same owner. The contrast
    with `uq_users_email_lower` is deliberate: `User` lowercases its address on
    construction, `TaskList` folds no case on its name.
    """
    ddl = _ddl(_table("task_lists"))

    assert (
        f"CONSTRAINT {constraints.UQ_TASK_LISTS_OWNER_ID_NAME} "
        "UNIQUE (owner_id, name)" in ddl
    )
    # Built from one template rather than written out twice: the two halves of
    # the contrast then cannot drift, and no artifact in the repository spells
    # the rejected form of this index as a literal.
    assert CASE_FOLDED_INDEX % "name" not in ddl
    assert CASE_FOLDED_INDEX % "email" in _ddl(_table("users"))


def test_status_and_priority_are_varchar_with_check_constraints() -> None:
    """DB-04 is enforced by named CHECK lists on VARCHAR, never a PG ENUM (D-11).

    A PostgreSQL `ENUM` would make adding a status a type migration instead of
    an ordinary `ALTER TABLE`, so the absence of `CREATE TYPE` is part of the
    claim, not an accident of how the DDL is rendered.
    """
    ddl = _ddl(_table("tasks"))

    assert "status VARCHAR(16)" in ddl
    assert "priority VARCHAR(16)" in ddl
    assert "status IN ('pending','in_progress','completed')" in ddl
    assert "priority IN ('low','medium','high')" in ddl
    assert "CREATE TYPE" not in ddl


def test_every_timestamp_column_is_timezone_aware() -> None:
    """Every timestamp is `TIMESTAMP WITH TIME ZONE`, so no instant loses its offset.

    The application always supplies UTC-aware values through the `Clock` port
    (Phase 2 D-13/D-14); a naive column would silently discard the offset on the
    way in and hand back a value the entity refuses on the way out.
    """
    timestamp_columns = [
        (table.name, column.name)
        for table in _tables()
        for column in _columns(table)
        if isinstance(column.type, DateTime)
    ]

    # Vacuity guard: eight timestamp columns exist across the three tables -
    # created_at/updated_at on each, plus tasks.due_date and tasks.completed_at.
    assert len(timestamp_columns) == 8

    naive = [
        (table.name, column.name)
        for table in _tables()
        for column in _columns(table)
        if isinstance(column.type, DateTime) and column.type.timezone is not True
    ]

    assert naive == []
    assert "TIMESTAMP WITHOUT TIME ZONE" not in _schema_ddl()


def test_foreign_keys_carry_the_d05_delete_rules() -> None:
    """Deleting a parent never leaves an orphan row or a dangling reference (DB-05).

    A deleted owner takes their lists and those lists' tasks with them; a deleted
    user who was merely assigned a task leaves the task standing, unassigned.
    """
    task_lists_ddl = _ddl(_table("task_lists"))
    tasks_ddl = _ddl(_table("tasks"))

    assert (
        f"CONSTRAINT {constraints.FK_TASK_LISTS_OWNER_ID_USERS} "
        "FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE"
        in task_lists_ddl
    )
    assert (
        f"CONSTRAINT {constraints.FK_TASKS_TASK_LIST_ID_TASK_LISTS} "
        "FOREIGN KEY(task_list_id) REFERENCES task_lists (id) ON DELETE CASCADE"
        in tasks_ddl
    )
    assert (
        f"CONSTRAINT {constraints.FK_TASKS_ASSIGNEE_ID_USERS} "
        "FOREIGN KEY(assignee_id) REFERENCES users (id) ON DELETE SET NULL" in tasks_ddl
    )


def test_no_column_declares_a_server_default() -> None:
    """The `Clock` port stays the only source of time (Phase 2 D-13/D-14).

    A `server_default=now()` would also be permanent `alembic check` drift,
    because the models would keep describing a column the database has extended.

    `users.full_name` is the one column a revision ever gave a default: `0002`
    adds it `NOT NULL` over populated tables and needs something to fill the
    existing rows with. The default is dropped in the same `upgrade()`, and this
    assertion is one half of the proof it did not survive - `alembic check`,
    which compares the live database against these models, is the other.
    """
    columns = [column for table in _tables() for column in _columns(table)]

    # Vacuity guard: twenty-three columns across the three tables.
    assert len(columns) == 23

    defaulted = [
        f"{column.table.name}.{column.name}"
        for column in columns
        if column.server_default is not None
    ]

    assert defaulted == []


def test_string_lengths_match_the_entity_caps() -> None:
    """Each `String(n)` repeats an entity `ClassVar`, so the two cannot disagree.

    The entity guard and the column width are the same rule stated twice, once
    per layer; this test is what keeps the second statement true.
    """
    assert _string_length("users", "email") == User.EMAIL_MAX_LENGTH
    assert _string_length("users", "full_name") == User.FULL_NAME_MAX_LENGTH
    assert _string_length("users", "password_hash") == User.PASSWORD_HASH_MAX_LENGTH
    assert _string_length("task_lists", "name") == TaskList.NAME_MAX_LENGTH
    assert (
        _string_length("task_lists", "description") == TaskList.DESCRIPTION_MAX_LENGTH
    )
    assert _string_length("tasks", "title") == Task.TITLE_MAX_LENGTH
    assert _string_length("tasks", "description") == Task.DESCRIPTION_MAX_LENGTH


def test_every_relationship_raises_on_lazy_load() -> None:
    """No relationship may emit SQL on attribute access (DB-03, roadmap SC-2).

    `lazy="raise"` converts what would be a `MissingGreenlet` at runtime, under
    async, into an `InvalidRequestError` the first time a developer writes the
    access. The walk covers every mapper, so a relationship added later without
    the setting fails here rather than in production.
    """
    relationships = [
        relationship
        for mapper in Base.registry.mappers
        for relationship in mapper.relationships
    ]

    # Vacuity guard: `TaskListRow.tasks` is the one declared relationship.
    assert [relationship.key for relationship in relationships] == ["tasks"]

    loud = [
        relationship.key
        for relationship in relationships
        if relationship.lazy != "raise"
    ]

    assert loud == []


def test_the_three_row_classes_are_not_the_three_entities() -> None:
    """DB-03 at its bluntest: the persistence classes are separate types.

    A test that only read the DDL would still pass if the entities themselves had
    been mapped imperatively, which is the shape DB-03 rules out.
    """
    assert {UserRow, TaskListRow, TaskRow}.isdisjoint({User, TaskList, Task})
    assert not issubclass(UserRow, User)
    assert [row.__tablename__ for row in (UserRow, TaskListRow, TaskRow)] == list(
        TABLE_NAMES
    )
