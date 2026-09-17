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
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
