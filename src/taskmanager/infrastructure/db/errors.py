"""The infrastructure faults this package raises, and nothing else.

D-13 and the CLAUDE.md error-handling rule share one boundary: no SQLAlchemy and
no psycopg exception type may be named above `taskmanager.infrastructure`. A
repository therefore either translates a driver failure into a `DomainError` it
already owns, or re-raises it untouched so the catch-all handler answers the
fixed 500 body. This module holds the small amount of vocabulary that
translation needs.

The rejected alternative is a grab-bag mapping table consulted by the
`UnitOfWork` at commit time. By then the failure has lost its author: the unit
of work knows a constraint was violated, not which repository wrote the row, so
it would have to guess which `DomainError` the use case deserves from the
constraint name alone - and guess wrongly the first time two aggregates share a
constraint prefix. A `flush()` inside each write method keeps the failure where
its meaning still is, and this module is what the method inspects it with.
"""


class NaiveDatetimeFromDatabaseError(RuntimeError):
    """A timestamp came back from the database with no timezone attached.

    This is the WR-05 decision written down in code. D-11 makes every timestamp
    column `TIMESTAMP WITH TIME ZONE`, and psycopg hands those back as aware
    values, so a naive one means the schema regressed away from what the
    migrations promise. That is a fault of this process's own storage, not a
    problem with anything a caller sent.

    Deliberately a `RuntimeError` and deliberately **not** a `DomainError`
    subclass. Phase 2's catch-all handler turns an unrecognised exception into
    the fixed 500 body with no message, which is exactly right here: there is no
    request field to name, and reporting a schema regression as a 422 validation
    problem would send a client looking for a mistake they did not make. D-14 is
    refined by scope, not overturned - a naive datetime *reaching the domain* is
    still a `ValidationError`.
    """

    def __init__(self, column: str) -> None:
        # The column name, and only the column name, is forwarded: flake8-bugbear
        # B042 requires every parameter to reach `super().__init__()`
        # positionally, and `Exception.__reduce__` rebuilds an instance by
        # calling `cls(*self.args)`. Handing the *message* up instead - the
        # obvious shape - would rebuild this error with its own message as the
        # column name after a `copy.copy()`. The message is therefore assembled
        # in `__str__` rather than stored, which is the same trade
        # `domain.exceptions.DomainError` makes for the same reason.
        super().__init__(column)
        self.column = column

    def __str__(self) -> str:
        """Name the column, and say what the schema was supposed to promise."""
        return (
            f"{self.column} was read from the database without a timezone; "
            "the column must be TIMESTAMP WITH TIME ZONE."
        )
