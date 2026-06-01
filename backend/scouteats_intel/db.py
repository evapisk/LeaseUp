"""SQLAlchemy 2.0 engine/session setup. Uses JSONB on Postgres, JSON elsewhere."""
from __future__ import annotations

from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

# JSONB on Postgres (per spec), plain JSON on SQLite for zero-setup local runs.
JSONColumn = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_connect_args = (
    {"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    _settings.database_url, pool_pre_ping=True, connect_args=_connect_args
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables. (Use Alembic for real migrations in production.)"""
    from . import models  # noqa: F401 - ensure models are registered

    Base.metadata.create_all(engine)
