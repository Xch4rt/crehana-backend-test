"""Where the integration-test database URL comes from (D-04), in one place.

The obvious shortcut is a substring substitution on `DATABASE_URL`, swapping the
word `taskmanager` for `taskmanager_test`. It is wrong here, and not
theoretically: the compose service and CI both authenticate as
`taskmanager:taskmanager@`, so the word appears three times in the very URL this
project ships. A substitution rewrites the username and the password along with
the database name and produces a URL that fails to authenticate - against a
server that is running, with credentials that are correct, which is the most
expensive kind of failure to read. `make_url(...).set(database=...)` parses the
URL and replaces exactly one component, leaving the user, the password, the host,
the port and any query string untouched.

`resolve_test_database_url` is the single expression of D-04's precedence, so no
fixture has to remember that an explicit `TEST_DATABASE_URL` outranks the
derivation.
"""

from typing import Final

from sqlalchemy.engine import make_url

from taskmanager.infrastructure.config.settings import Settings

# The D-04 database name: the one docker/initdb/01-create-test-database.sql
# creates beside the application database, and the one CI's service container
# already uses.
TEST_DATABASE_NAME: Final[str] = "taskmanager_test"


def derive_test_database_url(database_url: str) -> str:
    """Return `database_url` pointing at the test database instead (D-04)."""
    # hide_password=False because the result is a live connection string and a
    # masked password would produce an unusable URL. Any URL rendered into a
    # message - a log line, an exception, a fail-fast fixture - must instead use
    # the default `render_as_string()`, which masks it (threat T-3-10).
    return (
        make_url(database_url)
        .set(database=TEST_DATABASE_NAME)
        .render_as_string(hide_password=False)
    )


def resolve_test_database_url(settings: Settings) -> str:
    """Return the explicit test DSN when set, the derived one otherwise."""
    if settings.test_database_url is not None:
        return settings.test_database_url
    return derive_test_database_url(settings.database_url)
