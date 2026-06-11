"""Lender / Program / PolicyRule — the normalized policy schema.

The shape that lets five very different lender PDFs live in one model:

    Lender 1──* Program 1──* PolicyRule
       └────────────────────* PolicyRule   (lender-scoped knockouts)

* A **Lender** owns lender-wide knockout rules (industry/state/citizenship/BK
  exclusions that apply no matter which program).
* A **Program** is one tier / rate-grade / credit-box variant (Stearns "Tier 1",
  Apex "A+", Falcon "A", Citizens "Tier 1 General", ...). It carries its own
  qualification rules and optional prerequisite rules (applicability gates).
* A **PolicyRule** is a single declarative check: ``rule_type`` + ``config`` JSON
  + ``severity``. This is the unit you edit/add to change a policy — no code.

Programs are ranked (``rank`` 1 = best tier) and carry display metadata (rate,
buy-rate) used for "best matching program" selection and the fit score.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONType
from app.models.enums import RuleScope, RuleSeverity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lender(Base):
    __tablename__ = "lenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Free-form provenance / notes (source PDF, effective date, contact, ...).
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    programs: Mapped[list["Program"]] = relationship(
        back_populates="lender",
        cascade="all, delete-orphan",
        order_by="Program.rank",
    )
    rules: Mapped[list["PolicyRule"]] = relationship(
        back_populates="lender",
        cascade="all, delete-orphan",
        primaryjoin="and_(Lender.id==PolicyRule.lender_id, PolicyRule.program_id==None)",
        viewonly=False,
    )


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    lender_id: Mapped[int] = mapped_column(
        ForeignKey("lenders.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # Lower rank = better tier (Tier 1 / A+). Drives best-program selection + score.
    rank: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Display / pricing metadata (rate, buy_rate, notes) — not used for gating.
    rate: Mapped[float | None] = mapped_column(Float, default=None)
    credit_grade: Mapped[str | None] = mapped_column(String(10), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    lender: Mapped["Lender"] = relationship(back_populates="programs")
    rules: Mapped[list["PolicyRule"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        primaryjoin="Program.id==PolicyRule.program_id",
    )

    __table_args__ = (UniqueConstraint("lender_id", "name", name="uq_program_name"),)


class PolicyRule(Base):
    """One declarative policy check.

    ``rule_type`` is a key into the rule registry; ``config`` holds its
    parameters (thresholds/lists). ``severity`` decides how a failure is treated
    (knockout / qualification / prerequisite / preference). A rule is attached to
    either a Program (program-scoped) or directly to a Lender (lender-wide
    knockout, ``program_id`` NULL).
    """

    __tablename__ = "policy_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    lender_id: Mapped[int] = mapped_column(
        ForeignKey("lenders.id", ondelete="CASCADE"), index=True
    )
    program_id: Mapped[int | None] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True, default=None
    )
    rule_type: Mapped[str] = mapped_column(String(80), index=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default=RuleSeverity.QUALIFICATION.value)
    scope: Mapped[str] = mapped_column(String(20), default=RuleScope.PROGRAM.value)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    lender: Mapped["Lender"] = relationship(
        back_populates="rules",
        primaryjoin="and_(Lender.id==PolicyRule.lender_id, PolicyRule.program_id==None)",
        overlaps="program,rules",
    )
    program: Mapped["Program | None"] = relationship(
        back_populates="rules", overlaps="lender,rules"
    )
