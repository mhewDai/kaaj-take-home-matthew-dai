"""Underwriting run + match result persistence.

    UnderwritingRun 1──* MatchResult 1──* CriterionResultRow

* **UnderwritingRun** is one execution of the matching workflow over an
  application (status, derived-features snapshot, timing).
* **MatchResult** is the outcome for a single lender (eligible?, best program,
  fit score, ranked position, top-line reasons).
* **CriterionResultRow** persists every individual criterion outcome so the UI
  can render the full "met / not met and why" breakdown without re-running.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONType
from app.models.enums import RunStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UnderwritingRun(Base):
    __tablename__ = "underwriting_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING.value)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # Snapshot of the derived features the engine evaluated (audit / debugging).
    derived_features: Mapped[dict] = mapped_column(JSONType, default=dict)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    lender_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    application: Mapped["LoanApplication"] = relationship(back_populates="runs")  # noqa: F821
    results: Mapped[list["MatchResult"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="MatchResult.rank",
    )


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("underwriting_runs.id", ondelete="CASCADE"), index=True
    )
    lender_id: Mapped[int] = mapped_column(ForeignKey("lenders.id"), index=True)
    lender_name: Mapped[str] = mapped_column(String(200))
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    # Best qualifying program (if eligible).
    matched_program_id: Mapped[int | None] = mapped_column(Integer, default=None)
    matched_program_name: Mapped[str | None] = mapped_column(String(200), default=None)
    matched_program_rate: Mapped[float | None] = mapped_column(Float, default=None)
    # Top-line human reasons (rejection reasons when ineligible).
    reasons: Mapped[list] = mapped_column(JSONType, default=list)

    run: Mapped["UnderwritingRun"] = relationship(back_populates="results")
    criteria: Mapped[list["CriterionResultRow"]] = relationship(
        back_populates="match_result",
        cascade="all, delete-orphan",
        order_by="CriterionResultRow.id",
    )


class CriterionResultRow(Base):
    __tablename__ = "criterion_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_result_id: Mapped[int] = mapped_column(
        ForeignKey("match_results.id", ondelete="CASCADE"), index=True
    )
    # Which program this criterion belongs to (NULL = lender-level knockout).
    program_id: Mapped[int | None] = mapped_column(Integer, default=None)
    program_name: Mapped[str | None] = mapped_column(String(200), default=None)
    rule_type: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(String(200), default=None)
    actual: Mapped[str | None] = mapped_column(String(200), default=None)

    match_result: Mapped["MatchResult"] = relationship(back_populates="criteria")
