"""Application settings loaded from the environment or a local .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://taxdome:taxdome-local-only@127.0.0.1:55432/taxdome"
    )
    test_database_url: str = (
        "postgresql+psycopg://taxdome:taxdome-local-only@127.0.0.1:55432/taxdome_test"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return the process settings, cached for normal application use."""
    return Settings()
