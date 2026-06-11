"""Test fixtures.

Tests run against a throwaway SQLite database (no Docker/Postgres needed). We set
``DATABASE_URL`` *before* importing any app module so the global engine, session
factory and FastAPI startup all bind to the temp DB.
"""
from __future__ import annotations

import os
import tempfile

# Must be set before importing app.* (settings are cached at first import).
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.lender import Lender  # noqa: E402
from app.seed.seed_lenders import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Lender).count() == 0:
            seed(db)
    finally:
        db.close()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(fastapi_app) as c:
        yield c
