"""Application configuration.

Settings are read from environment variables (or a local .env file). The single
most important knob is ``DATABASE_URL`` which decides whether we talk to Postgres
(the production / docker-compose default) or SQLite (zero-infra local + tests).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+psycopg://user:password@host:port/dbname  (docker-compose default)
    # sqlite:///./local.db                                   (no-infra fallback)
    database_url: str = "postgresql+psycopg://kaaj:kaaj@localhost:5432/kaaj"

    # Comma separated list of allowed CORS origins for the React dev server.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Per-lender evaluation retry policy used by the in-process workflow.
    lender_eval_max_retries: int = 2
    lender_eval_retry_backoff_seconds: float = 0.1

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
