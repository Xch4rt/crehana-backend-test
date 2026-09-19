"""The half of D-13's error translation that needs no PostgreSQL to prove.

Only the `None` results are asserted here, and that is deliberate. A populated
`Diagnostic` is produced by libpq from a real server response; it has no public
constructor, and building a stand-in object with a `constraint_name` attribute
would prove that this module can read an attribute off an object the test wrote
itself - which is true of any implementation, including a broken one. The
positive branch is therefore proven where it is real, in the integration suites
of plans 03-06 and 03-07, by inserting a duplicate and asserting the
`DomainError` that comes back.

What *is* proven here is the property those suites cannot show: that an
unrecognised failure produces `None`, so the caller falls through to its bare
`raise` and the exception reaches the catch-all handler. That is the difference
between a 500 nobody expected and a 409 nobody earned.
"""

import copy

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from taskmanager.domain.exceptions import DomainError
from taskmanager.infrastructure.db.constraints import UQ_TASK_LISTS_OWNER_ID_NAME
from taskmanager.infrastructure.db.errors import (
    NaiveDatetimeFromDatabaseError,
    violated_constraint,
)

pytestmark = pytest.mark.unit


def test_an_unknown_constraint_is_not_swallowed() -> None:
    """A non-psycopg original is unknowable, so a caller must re-raise it."""
    error = IntegrityError("INSERT INTO task_lists ...", None, RuntimeError("boom"))

    name = violated_constraint(error)

    assert name is None
    # The shape of the call site this protects: the comparison fails, so the
    # repository falls through to `raise` rather than answering 409.
    assert name != UQ_TASK_LISTS_OWNER_ID_NAME


def test_a_missing_original_exception_is_unknowable() -> None:
    """`orig` is declared optional by SQLAlchemy; None must not crash the read."""
    error = IntegrityError("INSERT INTO task_lists ...", None, RuntimeError("boom"))
    error.orig = None

    assert violated_constraint(error) is None


def test_a_psycopg_error_carrying_no_constraint_name_is_unknowable() -> None:
    """The second real `None` path: right exception type, empty diagnostics.

    A `psycopg.Error` that never came from a server response has a `Diagnostic`
    whose every field is `None`, which is exactly what a driver-level failure -
    a dropped connection mid-statement - looks like. It passes the isinstance
    narrowing and must still be treated as unknowable.
    """
    error = IntegrityError("INSERT INTO task_lists ...", None, psycopg.Error("boom"))

    assert violated_constraint(error) is None


def test_no_statement_or_parameter_text_is_returned() -> None:
    """T-3-13: only a constraint name may leave this function, or nothing."""
    error = IntegrityError(
        "INSERT INTO users (email) VALUES ('victim@example.com')",
        {"email": "victim@example.com"},
        RuntimeError("boom"),
    )

    assert violated_constraint(error) is None


def test_the_naive_datetime_error_names_its_column() -> None:
    """A schema regression has to say which column regressed, or it is noise."""
    error = NaiveDatetimeFromDatabaseError(column="tasks.completed_at")

    assert error.column == "tasks.completed_at"
    assert "tasks.completed_at" in str(error)
    assert "TIMESTAMP WITH TIME ZONE" in str(error)


def test_the_naive_datetime_error_survives_a_copy() -> None:
    """`cls(*self.args)` has to rebuild the column, not the rendered message.

    This is the concrete failure flake8-bugbear's B042 points at, and the reason
    the column rather than the message is what reaches `super().__init__()`.
    """
    error = copy.copy(NaiveDatetimeFromDatabaseError(column="users.created_at"))

    assert error.column == "users.created_at"
    assert "users.created_at" in str(error)


def test_the_naive_datetime_error_is_not_a_domain_error() -> None:
    """WR-05 is a decision about classification, so assert the classification.

    If this ever became a `DomainError`, Phase 2's handler would answer a client
    4xx naming a column no request of theirs contains. As a plain `RuntimeError`
    it reaches the catch-all instead and becomes the fixed 500 body - which is
    what a schema that stopped promising `timestamptz` deserves.
    """
    assert not issubclass(NaiveDatetimeFromDatabaseError, DomainError)
    assert issubclass(NaiveDatetimeFromDatabaseError, RuntimeError)

    with pytest.raises(RuntimeError):
        raise NaiveDatetimeFromDatabaseError(column="tasks.created_at")
