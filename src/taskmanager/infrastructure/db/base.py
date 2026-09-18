"""The declarative `Base` whose naming convention *generates* the D-12 names.

The rejected alternative is hand-typing each constraint name three times: once
in a model's `__table_args__`, once in the baseline migration, and once more in
the `IntegrityError` translation D-13 keys on. Three copies drift silently, and
the copy that drifts first is always the third one - a renamed constraint turns
LIST-06's 409 into a 500, and no test fails, because the translation simply
stops matching a name nobody reads. With the convention below the name is
derived from the table and the columns, so `uq_task_lists_owner_id_name` is
written down exactly once, in `constraints.py`, and the schema agrees with it by
construction rather than by proofreading.

The one case the convention cannot serve is an expression index
(`uq_users_email_lower` over `lower(email)`): there is no `column_0_N_name` to
interpolate, so that single name is passed explicitly - from the same constant.
"""

from typing import Final

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    # `%(constraint_name)s` is the `name=` passed to `CheckConstraint`, so
    # `CheckConstraint(..., name="status")` on `tasks` renders `ck_tasks_status`.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """The declarative base every ORM row class in this package inherits from.

    `metadata` is replaced rather than configured after the fact: the naming
    convention has to be present before the first table is defined, because
    SQLAlchemy resolves constraint names at table-construction time.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
