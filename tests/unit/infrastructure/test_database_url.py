"""D-04: where the integration-test database URL comes from.

Two claims are pinned here. The first is that the derivation replaces the
database name and nothing else - the test that would catch a substring
substitution is `test_a_password_containing_taskmanager_is_not_rewritten`, and it
is written against the exact credential pair this project's compose file and CI
service both use, so the failure it guards against is the default case rather
than an exotic one. The second is D-04's precedence: an explicit
`TEST_DATABASE_URL` outranks the derivation, and `resolve_test_database_url` is
the only place that rule is expressed.
"""

import pytest

from taskmanager.infrastructure.config import database_url as module
from taskmanager.infrastructure.config.database_url import (
    derive_test_database_url,
    resolve_test_database_url,
)
from taskmanager.infrastructure.config.settings import Settings

# The compose and CI credential pair, verbatim: user and password both spell the
# word that also names the database.
COMPOSE_URL = "postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager"
COMPOSE_TEST_URL = (
    "postgresql+psycopg://taskmanager:taskmanager@localhost:5432/taskmanager_test"
)

# An obviously fake secret, long enough for the 16-character floor.
JWT_SECRET = "c" * 32


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    """Build Settings from an environment this test controls entirely."""
    monkeypatch.setenv("DATABASE_URL", COMPOSE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_the_database_name_is_replaced() -> None:
    """A plain URL comes back pointing at taskmanager_test."""
    url = "postgresql+psycopg://alice:secret@db:5432/taskmanager"

    assert (
        derive_test_database_url(url)
        == "postgresql+psycopg://alice:secret@db:5432/taskmanager_test"
    )


def test_a_password_containing_taskmanager_is_not_rewritten() -> None:
    """The user and the password survive; only the trailing name changes."""
    derived = derive_test_database_url(COMPOSE_URL)

    assert derived == COMPOSE_TEST_URL
    # Spelled out, because this is the whole point of the module: three
    # occurrences of the word go in, exactly one of them is touched.
    assert "//taskmanager:taskmanager@" in derived


def test_query_parameters_survive_the_swap() -> None:
    """Connection options carried in the query string are preserved."""
    url = COMPOSE_URL + "?sslmode=require"

    assert derive_test_database_url(url) == COMPOSE_TEST_URL + "?sslmode=require"


def test_an_explicit_test_database_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST_DATABASE_URL outranks the derivation and is returned verbatim."""
    explicit = "postgresql+psycopg://other:pass@127.0.0.1:55432/somewhere_else"
    settings = _settings(monkeypatch, TEST_DATABASE_URL=explicit)

    def _fail(_: str) -> str:
        raise AssertionError("the derivation must not run when the setting is set")

    monkeypatch.setattr(module, "derive_test_database_url", _fail)

    assert resolve_test_database_url(settings) == explicit


def test_the_derivation_is_used_when_the_setting_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With TEST_DATABASE_URL unset, DATABASE_URL is the source."""
    settings = _settings(monkeypatch)

    assert settings.test_database_url is None
    assert resolve_test_database_url(settings) == COMPOSE_TEST_URL
