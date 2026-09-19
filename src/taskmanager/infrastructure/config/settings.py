"""Application settings loaded from the process environment.

`database_url` and `jwt_secret` deliberately carry no default: a misconfigured
process must fail at boot with a single readable ValidationError listing every
missing variable, rather than starting up on a placeholder secret and failing
at the first authenticated request. The placeholder half of that promise is
kept by the validator below, which refuses the value `.env.example` publishes
(ADR-084).
"""

from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The opening of the value `.env.example` ships. The rule is the prefix rather
# than the whole string, so a half-edited copy of it is refused too (ADR-084).
_PLACEHOLDER_PREFIX: Final[str] = "replace-me"


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
    # `make env && docker compose up` in production, not just in tests. `None`
    # is the default, so no secret gains one.
    test_database_url: str | None = None
    # D-26, threat T-5-02. The floor was 16 and is now 32. RFC 7518 §3.2
    # requires an HMAC key at least as long as the hash output, which for HS256
    # is 32 bytes, and PyJWT enforces that by warning on both encode and decode
    # below it. `pytest.ini` sets `filterwarnings = error`, so a shorter secret
    # would not merely be weak: it would make an unrelated test fail with an
    # `InsecureKeyLengthWarning` and no assertion anywhere in the traceback,
    # which is the hardest kind of failure to read. Refusing it at boot turns
    # that into one readable ValidationError naming this field. A length is not
    # a secret, though: `.env.example`'s 34-character placeholder cleared the
    # floor and was therefore accepted, which is how the documented setup came
    # to sign every token with a value published in this repository. It is now
    # refused by name as well (ADR-084). `tests/conftest.py` (32) and CI (36)
    # clear both rules and are not placeholders.
    jwt_secret: str = Field(min_length=32)
    # A closed set of one. The adapter signs with a shared secret, and the floor
    # above is the HS256 floor specifically - HS512 would need 64 bytes, so it
    # is excluded rather than accepted against a floor sized for something else.
    # A free string let `none`, `RS256` or a trailing space boot cleanly and
    # then fail every login (WR-03).
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=30, gt=0)

    @field_validator("jwt_secret")
    @classmethod
    def _refuse_the_published_placeholder(cls, value: str) -> str:
        """Refuse the secret `.env.example` ships, and half-edited copies of it.

        This is a prefix rule and nothing more: it stops the one value a reader
        of the public repository already has, not a weak secret an operator
        types themselves. The message names the remedy, because a refusal an
        evaluator cannot act on is only half of the fix.
        """
        if value.casefold().startswith(_PLACEHOLDER_PREFIX):
            raise ValueError(
                "JWT_SECRET is still the .env.example placeholder. "
                "Run `make env` to write a generated secret into .env."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance, built once and reused."""
    return Settings()
