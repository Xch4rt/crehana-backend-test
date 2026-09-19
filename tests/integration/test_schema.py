"""Roadmap SC-3: what the migration actually built, read back from PostgreSQL.

Every assertion below is made against the live catalogue - reflected foreign
keys, `information_schema.columns`, `pg_type` - and not against `Base.metadata`.
That is the point. `tests/unit/infrastructure/test_models.py` already asserts the
same properties on the ORM side, where no database is needed; running both is
what makes a divergence between the models and the revision visible, because a
claim that holds in one place and not the other fails exactly one of the two
suites and names which.

`alembic check` covers part of this ground, but only part: it compares tables,
columns and types, and it is blind to `CHECK` constraints entirely. The foreign
keys, the cascade actions and the timestamp round trip are proven here; the
CHECKs are proven in `test_constraints.py`, by inserts PostgreSQL refuses.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import String, create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.pool import NullPool

from taskmanager.infrastructure.db.constraints import (
    FK_TASK_LISTS_OWNER_ID_USERS,
    FK_TASKS_ASSIGNEE_ID_USERS,
    FK_TASKS_TASK_LIST_ID_TASK_LISTS,
)

pytestmark = pytest.mark.integration

DOMAIN_TABLES = frozenset({"users", "task_lists", "tasks"})

# The width both enumerated columns are declared with (D-11). Named once so the
# two assertions below cannot drift apart from each other.
ENUM_COLUMN_WIDTH = 16

# Fixed literals throughout: a generated UUID or a `now()` would make the
# round-trip assertion below pass for a value the test never chose, which is the
# one thing it is trying to rule out. The microseconds are non-zero on purpose -
# a truncating column would still round-trip a value ending in six zeroes.
USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
CREATED_AT = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=UTC)


@pytest.fixture
def schema(migrated_database: None, database_url: str) -> Iterator[Connection]:
    """A synchronous connection for reflection and catalogue queries.

    Synchronous because reflection is: `Inspector` has no async form, and these
    tests write nothing, so they need none of the isolation the async
    `connection` fixture provides. It is a separate connection from that one and
    deliberately so - it reads committed schema, not uncommitted rows.
    """
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def _columns(connection: Connection) -> list[tuple[str, str, str, str | None]]:
    """(table, column, data type, default) for every column of the public schema."""
    rows = connection.execute(
        text(
            "SELECT table_name, column_name, data_type, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
    ).all()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def test_task_lists_has_an_owner_id_foreign_key(schema: Connection) -> None:
    """DB-05: a list belongs to a user, and dies with them."""
    foreign_keys = inspect(schema).get_foreign_keys("task_lists")

    assert len(foreign_keys) == 1
    owner = foreign_keys[0]
    assert owner["name"] == FK_TASK_LISTS_OWNER_ID_USERS
    assert owner["referred_table"] == "users"
    assert owner["constrained_columns"] == ["owner_id"]
    assert owner["options"]["ondelete"] == "CASCADE"

    # NOT NULL is half of the ownership rule: a cascade cannot protect a row that
    # was allowed to have no owner in the first place.
    owner_id = next(
        column
        for column in inspect(schema).get_columns("task_lists")
        if column["name"] == "owner_id"
    )
    assert owner_id["nullable"] is False


def test_tasks_reference_their_list_and_their_assignee(schema: Connection) -> None:
    """The two foreign keys of `tasks` differ on purpose, in both directions."""
    by_name = {
        foreign_key["name"]: foreign_key
        for foreign_key in inspect(schema).get_foreign_keys("tasks")
    }
    columns = {
        column["name"]: column for column in inspect(schema).get_columns("tasks")
    }

    parent = by_name[FK_TASKS_TASK_LIST_ID_TASK_LISTS]
    assert parent["referred_table"] == "task_lists"
    assert parent["constrained_columns"] == ["task_list_id"]
    assert parent["options"]["ondelete"] == "CASCADE"
    assert columns["task_list_id"]["nullable"] is False

    # SET NULL, not CASCADE, and nullable to make that possible: deleting a user
    # must un-assign their tasks, never delete work that belongs to a list.
    assignee = by_name[FK_TASKS_ASSIGNEE_ID_USERS]
    assert assignee["referred_table"] == "users"
    assert assignee["constrained_columns"] == ["assignee_id"]
    assert assignee["options"]["ondelete"] == "SET NULL"
    assert columns["assignee_id"]["nullable"] is True


def test_status_and_priority_are_varchar_not_postgres_enums(
    schema: Connection,
) -> None:
    """D-11: the enumerations live in CHECK constraints, not in the type system.

    A PostgreSQL `ENUM` would look tidier in `\\d tasks` and cost more than it
    saves: adding a member is a migration that cannot be reversed at all, and on
    older servers cannot run inside a transaction. A `VARCHAR` with a named CHECK
    is an ordinary `ALTER TABLE` in both directions.
    """
    columns = {
        column["name"]: column for column in inspect(schema).get_columns("tasks")
    }

    for name in ("status", "priority"):
        column_type = columns[name]["type"]
        assert isinstance(column_type, String), (name, column_type)
        assert column_type.length == ENUM_COLUMN_WIDTH, name

    user_defined_enums = schema.scalar(
        text(
            "SELECT count(*) FROM pg_type AS t "
            "JOIN pg_namespace AS n ON n.oid = t.typnamespace "
            "WHERE t.typtype = 'e' AND n.nspname = 'public'"
        )
    )
    assert user_defined_enums == 0


def test_every_timestamp_column_is_timestamptz(schema: Connection) -> None:
    """D-11: no column in this schema can store an ambiguous instant."""
    timestamps = [
        (table, column, data_type)
        for table, column, data_type, _ in _columns(schema)
        if table in DOMAIN_TABLES and data_type.startswith("timestamp")
    ]

    # Vacuity guard: a renamed table or an empty reflection would otherwise make
    # the assertion below true about nothing at all.
    assert timestamps
    assert [
        entry for entry in timestamps if entry[2] != "timestamp with time zone"
    ] == []


def test_no_column_has_a_server_default(schema: Connection) -> None:
    """The `Clock` port stays the only source of time (Phase 2 D-13/D-14).

    A `DEFAULT now()` on `created_at` would look harmless and quietly take the
    decision away from the application: a use case could then omit the value and
    still get a row, and the fake clock every unit test injects would stop being
    the only thing that decides what "now" means. It would also show up as
    permanent `alembic check` drift, since no model declares it.
    """
    defaults = [
        (table, column, default)
        for table, column, _, default in _columns(schema)
        if table in DOMAIN_TABLES and default is not None
    ]

    assert defaults == []


async def test_timestamps_round_trip_as_aware_utc(connection: AsyncConnection) -> None:
    """The empirical answer to RESEARCH assumption A4, written down once.

    The mappers refuse a naive datetime read from a row
    (`NaiveDatetimeFromDatabaseError`), and that guard is only a tripwire if the
    schema genuinely hands back aware values. This is the test that says it does,
    against a real server rather than against the assumption.

    The offset assertion pins the session timezone as much as the column type -
    the compose database and the CI service container both run UTC, and a server
    that did not would be a configuration problem this suite should report rather
    than absorb. The equality that follows is offset-independent and is the
    stronger claim: the instant that came back is the instant that went in.
    """
    await connection.execute(
        text(
            "INSERT INTO users "
            "(id, email, full_name, password_hash, created_at, updated_at) "
            "VALUES (:id, :email, :full_name, :password_hash, :created_at, "
            ":updated_at)"
        ),
        {
            "id": USER_ID,
            "email": "aware@example.test",
            "full_name": "Aware Person",
            "password_hash": "hashed-" + "x" * 20,
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
        },
    )

    stored = await connection.scalar(
        text("SELECT created_at FROM users WHERE id = :id"), {"id": USER_ID}
    )

    assert isinstance(stored, datetime)
    assert stored.tzinfo is not None
    assert stored.utcoffset() == timedelta(0)
    assert stored == CREATED_AT
