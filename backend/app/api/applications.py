"""Loan application CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.application import (
    Business,
    BusinessCredit,
    Equipment,
    Guarantor,
    LoanApplication,
    LoanRequest,
)
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationSummary,
    ApplicationUpdate,
)

router = APIRouter(tags=["applications"])

_LOAD = (
    selectinload(LoanApplication.business),
    selectinload(LoanApplication.guarantor),
    selectinload(LoanApplication.business_credit),
    selectinload(LoanApplication.loan_request),
    selectinload(LoanApplication.equipment),
)


def _load(db: Session, app_id: int) -> LoanApplication:
    app = (
        db.query(LoanApplication)
        .options(*_LOAD)
        .filter(LoanApplication.id == app_id)
        .first()
    )
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return app


def _enum_value(v):
    return v.value if hasattr(v, "value") else v


def _build_children(app: LoanApplication, payload: ApplicationCreate | ApplicationUpdate) -> None:
    if payload.business is not None:
        data = payload.business.model_dump()
        data["industry"] = _enum_value(data["industry"])
        data["state"] = data["state"].upper()
        app.business = Business(**data)
    if payload.guarantor is not None:
        app.guarantor = Guarantor(**payload.guarantor.model_dump())
    if payload.business_credit is not None:
        app.business_credit = BusinessCredit(**payload.business_credit.model_dump())
    if payload.loan_request is not None:
        app.loan_request = LoanRequest(**payload.loan_request.model_dump())
    if payload.equipment is not None:
        data = payload.equipment.model_dump()
        data["equipment_type"] = _enum_value(data["equipment_type"])
        data["condition"] = _enum_value(data.get("condition"))
        app.equipment = Equipment(**data)


@router.get("/applications", response_model=list[ApplicationSummary])
def list_applications(db: Session = Depends(get_db)) -> list[ApplicationSummary]:
    apps = (
        db.query(LoanApplication)
        .options(selectinload(LoanApplication.business), selectinload(LoanApplication.loan_request))
        .order_by(LoanApplication.id.desc())
        .all()
    )
    return [
        ApplicationSummary(
            id=a.id, reference=a.reference, status=a.status,
            business_name=a.business.legal_name if a.business else None,
            amount=a.loan_request.amount if a.loan_request else None,
        )
        for a in apps
    ]


@router.get("/applications/{app_id}", response_model=ApplicationRead)
def get_application(app_id: int, db: Session = Depends(get_db)) -> LoanApplication:
    return _load(db, app_id)


@router.post("/applications", response_model=ApplicationRead,
             status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> LoanApplication:
    app = LoanApplication(reference=payload.reference, status="submitted")
    _build_children(app, payload)
    db.add(app)
    db.commit()
    return _load(db, app.id)


@router.put("/applications/{app_id}", response_model=ApplicationRead)
def replace_application(
    app_id: int, payload: ApplicationCreate, db: Session = Depends(get_db)
) -> LoanApplication:
    app = _load(db, app_id)
    app.reference = payload.reference
    # Clear and rebuild children for a full replace.
    app.business = None
    app.guarantor = None
    app.business_credit = None
    app.loan_request = None
    app.equipment = None
    db.flush()
    _build_children(app, payload)
    db.commit()
    return _load(db, app_id)


@router.patch("/applications/{app_id}", response_model=ApplicationRead)
def update_application(
    app_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)
) -> LoanApplication:
    app = _load(db, app_id)
    if payload.reference is not None:
        app.reference = payload.reference
    # Only the provided sections are replaced.
    _build_children(app, payload)
    db.commit()
    return _load(db, app_id)


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_application(app_id: int, db: Session = Depends(get_db)) -> Response:
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    db.delete(app)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
