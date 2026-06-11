"""FastAPI application entrypoint.

Wires the routers under ``/api``, configures CORS for the React dev server, and
(for convenience in this take-home) creates tables + seeds lenders on startup if
the database is empty. A production deployment would run migrations + seeding as
separate steps instead.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import applications, lenders, underwriting
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.lender import Lender

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create tables + seed lenders on startup if the DB is empty.

    Convenient for this take-home; production would run migrations + seeding as
    separate, explicit steps.
    """
    init_db()
    db = SessionLocal()
    try:
        if db.query(Lender).count() == 0:
            from app.seed.seed_lenders import seed

            logging.getLogger("startup").info("Empty DB — seeding lenders…")
            seed(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Lender Matching Platform",
    version="1.0.0",
    description="Loan underwriting + lender matching against normalized credit policies.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lenders.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(underwriting.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
