"""Database engine, session factory and declarative base.

We keep the ORM portable so the exact same models run on Postgres (production /
docker-compose) and SQLite (used by the test-suite, so tests need zero infra).
The only dialect-specific touch is the ``JSONType`` helper which upgrades to
``JSONB`` on Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread off when shared across the request threads.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Portable JSON column: JSONB on Postgres, plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Used at startup and by the seed script.

    A real deployment would use Alembic migrations; ``create_all`` keeps the
    take-home runnable with a single command (see DECISIONS.md).
    """
    from app import models  # noqa: F401  (ensure models are imported/registered)

    Base.metadata.create_all(bind=engine)
