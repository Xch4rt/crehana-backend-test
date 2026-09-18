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
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
