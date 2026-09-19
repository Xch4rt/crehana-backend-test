"""Application settings loaded from the process environment.

`database_url` and `jwt_secret` deliberately carry no default: a misconfigured
process must fail at boot with a single readable ValidationError listing every
missing variable, rather than starting up on a placeholder secret and failing
at the first authenticated request.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every configurable value of the application, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # An unknown key in .env is a typo, not a no-op: fail loudly.
        extra="forbid",
        # Settings are read-only once loaded.
        frozen=True,
    )

    app_name: str = "Task Manager API"
    environment: str = "local"
    database_url: str
    # Test-only (D-04): nothing in the running application ever reads it, and
    # `tests/integration/conftest.py` falls back to deriving the URL from
    # `database_url` when it is unset. It is declared here anyway because the
    # two ends of the configuration contract cannot be separated: the key must
    # exist in `.env.example` and in this class, or in neither. `.env.example`
    # parity is an exact set equality, and `extra="forbid"` turns an undeclared
    # key present in a copied `.env` into a boot-time ValidationError - so
    # documenting the key without declaring the field would break
    # `cp .env.example .env && docker compose up` in production, not just in
    # tests. `None` is the default, so no secret gains one.
    test_database_url: str | None = None
    # D-26, threat T-5-02. The floor was 16 and is now 32. RFC 7518 §3.2
    # requires an HMAC key at least as long as the hash output, which for HS256
    # is 32 bytes, and PyJWT enforces that by warning on both encode and decode
    # below it. `pytest.ini` sets `filterwarnings = error`, so a shorter secret
    # would not merely be weak: it would make an unrelated test fail with an
    # `InsecureKeyLengthWarning` and no assertion anywhere in the traceback,
    # which is the hardest kind of failure to read. Refusing it at boot turns
    # that into one readable ValidationError naming this field. Every secret
    # already in the repository clears the new floor (`tests/conftest.py` 32,
    # `.env.example` 34, CI 36), so nothing had to be lengthened with it.
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
