"""Underwriting run initiation, status, and match-results retrieval."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.application import LoanApplication
from app.models.result import MatchResult, UnderwritingRun
from app.schemas.result import MatchResultRead, RunRead, RunSummary
from app.workflow.orchestrator import run_underwriting_sync

router = APIRouter(tags=["underwriting"])


def _load_run(db: Session, run_id: int) -> UnderwritingRun:
    run = (
        db.query(UnderwritingRun)
        .options(
            selectinload(UnderwritingRun.results).selectinload(MatchResult.criteria)
        )
        .filter(UnderwritingRun.id == run_id)
        .first()
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


@router.post("/applications/{app_id}/underwrite", response_model=RunRead,
             status_code=status.HTTP_201_CREATED)
def start_underwriting(app_id: int, db: Session = Depends(get_db)) -> UnderwritingRun:
    """Initiate an underwriting run over all active lenders.

    The run is created (status PENDING) then executed by the workflow
    orchestrator. The completed run — including ranked match results and the full
    per-criterion breakdown — is returned. ``GET /runs/{id}`` retrieves it later.
    """
    app = (
        db.query(LoanApplication)
        .options(
            selectinload(LoanApplication.business),
            selectinload(LoanApplication.guarantor),
            selectinload(LoanApplication.business_credit),
            selectinload(LoanApplication.loan_request),
            selectinload(LoanApplication.equipment),
        )
        .filter(LoanApplication.id == app_id)
        .first()
    )
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    run = UnderwritingRun(application_id=app_id)
    db.add(run)
    db.commit()

    run_underwriting_sync(db, run)
    return _load_run(db, run.id)


@router.get("/applications/{app_id}/runs", response_model=list[RunSummary])
def list_runs(app_id: int, db: Session = Depends(get_db)) -> list[UnderwritingRun]:
    return (
        db.query(UnderwritingRun)
        .filter(UnderwritingRun.application_id == app_id)
        .order_by(UnderwritingRun.created_at.desc())
        .all()
    )


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: int, db: Session = Depends(get_db)) -> UnderwritingRun:
    return _load_run(db, run_id)


@router.get("/runs/{run_id}/results", response_model=list[MatchResultRead])
def get_run_results(run_id: int, db: Session = Depends(get_db)) -> list[MatchResult]:
    run = _load_run(db, run_id)
    return run.results
