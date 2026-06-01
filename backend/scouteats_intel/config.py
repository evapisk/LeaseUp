"""Env-driven configuration. All vars are prefixed SCOUTEATS_ (e.g.
SCOUTEATS_SOCRATA_APP_TOKEN, SCOUTEATS_DATABASE_URL)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCOUTEATS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Socrata
    socrata_base_url: str = "https://data.cityofnewyork.us/resource"
    socrata_app_token: str | None = None
    dataset_dohmh: str = "43nn-pn8j"  # DOHMH Restaurant Inspection Results

    # HTTP
    request_timeout_seconds: float = 30.0
    request_retries: int = 3
    batch_size: int = 1000

    # Persistence. Defaults to local SQLite so the backend runs with no setup;
    # point at Postgres for JSONB columns, e.g.
    #   postgresql+psycopg://user:pass@localhost:5432/scouteats
    database_url: str = "sqlite+pysqlite:///./scouteats.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
