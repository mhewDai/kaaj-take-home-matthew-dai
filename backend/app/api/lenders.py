"""Lender / program / policy-rule management API.

These endpoints back the policy screen and make the system *editable*: changing a
threshold is a PATCH on a rule's ``config``; adding a check is a POST of a new
rule; adding a lender is a POST of a normalized lender payload. None of this
requires code changes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.enums import (
    EquipmentType,
    Industry,
    RuleScope,
    RuleSeverity,
)
from app.models.lender import Lender, PolicyRule, Program
from app.rules import registry
from app.schemas.lender import (
    LenderCreate,
    LenderRead,
    LenderSummary,
    LenderUpdate,
    PolicyRuleCreate,
    PolicyRuleRead,
    PolicyRuleUpdate,
    ProgramCreate,
    ProgramRead,
    ProgramUpdate,
    RuleTypeRead,
)
from app.seed.seed_lenders import create_lender_from_dict

router = APIRouter(tags=["lenders"])


# --------------------------------------------------------------------------- #
# Reference data for the UI
# --------------------------------------------------------------------------- #
@router.get("/rule-types", response_model=list[RuleTypeRead])
def list_rule_types() -> list[dict]:
    """Every available policy-check type and its editable parameters."""
    return [rt.to_dict() for rt in registry.all()]


@router.get("/enums")
def list_enums() -> dict[str, list[str]]:
    """Controlled vocabularies for form dropdowns / rule editors."""
    return {
        "industries": [i.value for i in Industry],
        "equipment_types": [e.value for e in EquipmentType],
        "severities": [s.value for s in RuleSeverity],
    }


# --------------------------------------------------------------------------- #
# Lender CRUD
# --------------------------------------------------------------------------- #
def _load_lender(db: Session, lender_id: int) -> Lender:
    lender = (
        db.query(Lender)
        .options(
            selectinload(Lender.programs).selectinload(Program.rules),
            selectinload(Lender.rules),
        )
        .filter(Lender.id == lender_id)
        .first()
    )
    if lender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lender not found")
    return lender


@router.get("/lenders", response_model=list[LenderSummary])
def list_lenders(db: Session = Depends(get_db)) -> list[LenderSummary]:
    lenders = db.query(Lender).order_by(Lender.name).all()
    return [
        LenderSummary(
            id=ln.id, name=ln.name, slug=ln.slug, description=ln.description,
            is_active=ln.is_active, program_count=len(ln.programs),
        )
        for ln in lenders
    ]


@router.get("/lenders/{lender_id}", response_model=LenderRead)
def get_lender(lender_id: int, db: Session = Depends(get_db)) -> Lender:
    return _load_lender(db, lender_id)


@router.post("/lenders", response_model=LenderRead, status_code=status.HTTP_201_CREATED)
def create_lender(payload: LenderCreate, db: Session = Depends(get_db)) -> Lender:
    if db.query(Lender).filter(Lender.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Slug '{payload.slug}' already exists")
    data = payload.model_dump()
    # Normalize to the seed builder's shape (rules carry rule_type/config/severity).
    lender = create_lender_from_dict(db, data)
    db.commit()
    return _load_lender(db, lender.id)


@router.patch("/lenders/{lender_id}", response_model=LenderRead)
def update_lender(
    lender_id: int, payload: LenderUpdate, db: Session = Depends(get_db)
) -> Lender:
    lender = _load_lender(db, lender_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lender, field, value)
    db.commit()
    return _load_lender(db, lender_id)


@router.delete("/lenders/{lender_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_lender(lender_id: int, db: Session = Depends(get_db)) -> Response:
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if lender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lender not found")
    db.delete(lender)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Program CRUD
# --------------------------------------------------------------------------- #
@router.post("/lenders/{lender_id}/programs", response_model=ProgramRead,
             status_code=status.HTTP_201_CREATED)
def create_program(
    lender_id: int, payload: ProgramCreate, db: Session = Depends(get_db)
) -> Program:
    _load_lender(db, lender_id)  # 404 if missing
    program = Program(
        lender_id=lender_id,
        **payload.model_dump(exclude={"rules"}),
    )
    db.add(program)
    db.flush()
    for r in payload.rules:
        db.add(_make_rule(r, lender_id=lender_id, program_id=program.id,
                          scope=RuleScope.PROGRAM))
    db.commit()
    db.refresh(program)
    return program


@router.patch("/programs/{program_id}", response_model=ProgramRead)
def update_program(
    program_id: int, payload: ProgramUpdate, db: Session = Depends(get_db)
) -> Program:
    program = db.query(Program).filter(Program.id == program_id).first()
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(program, field, value)
    db.commit()
    db.refresh(program)
    return program


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_program(program_id: int, db: Session = Depends(get_db)) -> Response:
    program = db.query(Program).filter(Program.id == program_id).first()
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")
    db.delete(program)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Policy-rule CRUD (the unit you edit to change a policy)
# --------------------------------------------------------------------------- #
def _make_rule(r: PolicyRuleCreate, *, lender_id: int, program_id: int | None,
               scope: RuleScope) -> PolicyRule:
    if not registry.has(r.rule_type):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown rule type '{r.rule_type}'")
    return PolicyRule(
        lender_id=lender_id, program_id=program_id, scope=scope.value,
        rule_type=r.rule_type, config=r.config,
        severity=r.severity.value if isinstance(r.severity, RuleSeverity) else r.severity,
        description=r.description, is_active=r.is_active,
    )


@router.post("/programs/{program_id}/rules", response_model=PolicyRuleRead,
             status_code=status.HTTP_201_CREATED)
def add_program_rule(
    program_id: int, payload: PolicyRuleCreate, db: Session = Depends(get_db)
) -> PolicyRule:
    program = db.query(Program).filter(Program.id == program_id).first()
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Program not found")
    rule = _make_rule(payload, lender_id=program.lender_id, program_id=program_id,
                      scope=RuleScope.PROGRAM)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/lenders/{lender_id}/rules", response_model=PolicyRuleRead,
             status_code=status.HTTP_201_CREATED)
def add_lender_rule(
    lender_id: int, payload: PolicyRuleCreate, db: Session = Depends(get_db)
) -> PolicyRule:
    """Add a lender-wide knockout / gate rule (applies to all programs)."""
    _load_lender(db, lender_id)
    rule = _make_rule(payload, lender_id=lender_id, program_id=None,
                      scope=RuleScope.LENDER)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=PolicyRuleRead)
def update_rule(
    rule_id: int, payload: PolicyRuleUpdate, db: Session = Depends(get_db)
) -> PolicyRule:
    rule = db.query(PolicyRule).filter(PolicyRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    updates = payload.model_dump(exclude_unset=True)
    if "rule_type" in updates and not registry.has(updates["rule_type"]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown rule type '{updates['rule_type']}'")
    if "severity" in updates and isinstance(updates["severity"], RuleSeverity):
        updates["severity"] = updates["severity"].value
    for field, value in updates.items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> Response:
    rule = db.query(PolicyRule).filter(PolicyRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
