"""Seed the database with the five normalized lender policies.

Run directly:  python -m app.seed.seed_lenders [--reset]

The same ``create_lender_from_dict`` builder backs both seeding and the
POST /lenders API, so the on-disk seed format and the API payload format are the
same normalized shape.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models.enums import RuleScope, RuleSeverity
from app.models.lender import Lender, PolicyRule, Program
from app.seed.lender_data import ALL_LENDERS


def create_lender_from_dict(db: Session, data: dict) -> Lender:
    lender = Lender(
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        is_active=data.get("is_active", True),
        metadata_json=data.get("metadata_json", {}),
    )
    db.add(lender)
    db.flush()  # assign lender.id

    # Lender-wide rules (knockouts / lender-level gates) — program_id stays NULL.
    for r in data.get("rules", []):
        db.add(_build_rule(r, lender_id=lender.id, program_id=None,
                           scope=RuleScope.LENDER))

    # Programs + their rules.
    for p in data.get("programs", []):
        program = Program(
            lender_id=lender.id,
            name=p["name"],
            rank=p.get("rank", 1),
            rate=p.get("rate"),
            credit_grade=p.get("credit_grade"),
            notes=p.get("notes"),
            metadata_json=p.get("metadata_json", {}),
        )
        db.add(program)
        db.flush()
        for r in p.get("rules", []):
            db.add(_build_rule(r, lender_id=lender.id, program_id=program.id,
                               scope=RuleScope.PROGRAM))
    return lender


def _build_rule(r: dict, *, lender_id: int, program_id: int | None,
                scope: RuleScope) -> PolicyRule:
    return PolicyRule(
        lender_id=lender_id,
        program_id=program_id,
        rule_type=r["rule_type"],
        config=r.get("config", {}),
        severity=r.get("severity", RuleSeverity.QUALIFICATION.value),
        scope=scope.value,
        description=r.get("description"),
    )


def seed(db: Session, *, reset: bool = False) -> int:
    if reset:
        for lender in db.query(Lender).all():
            db.delete(lender)
        db.flush()

    existing = {slug for (slug,) in db.query(Lender.slug).all()}
    created = 0
    for data in ALL_LENDERS:
        if data["slug"] in existing:
            print(f"  • {data['name']} already present — skipping")
            continue
        create_lender_from_dict(db, data)
        created += 1
        print(f"  ✓ seeded {data['name']}")
    db.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed lender policies")
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing lenders before seeding")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        count = seed(db, reset=args.reset)
        print(f"Done. {count} lender(s) seeded.")
    finally:
        db.close()
    if count == 0 and not args.reset:
        sys.exit(0)


if __name__ == "__main__":
    main()
