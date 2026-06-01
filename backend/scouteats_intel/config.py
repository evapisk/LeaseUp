"""Env-driven configuration. All vars are prefixed SCOUTEATS_ (e.g.
SCOUTEATS_SOCRATA_APP_TOKEN, SCOUTEATS_DATABASE_URL)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


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

    # Local datasets merged into /listings alongside the live Socrata feed.
    local_inspections_path: str = str(
        _REPO_ROOT / "frontend" / "public" / "data" / "inspections.json"
    )
    manhattan_closed_path: str = str(_REPO_ROOT / "MANHATTAN_CLOSED.json")

    # Codify (codify.cafe = P2X Laravel api) AI enrichment integration.
    # Absent token or unreachable host degrades gracefully to a local fallback.
    codify_enabled: bool = True
    codify_base_url: str = "https://api.codify.inc"
    codify_token: str | None = None
    codify_x_domain: str = "codify.cafe"  # the tenant value, NOT the host
    codify_subproject_id: int | None = None
    codify_pipe_name: str = "restaurant_lease_takeover"
    codify_timeout_seconds: float = 20.0
    codify_public_base_url: str = "https://codify.cafe"


@lru_cache
def get_settings() -> Settings:
    return Settings()
