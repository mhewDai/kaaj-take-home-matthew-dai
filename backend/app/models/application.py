"""Loan application aggregate.

Modeled as the distinct entities the brief calls out, each 1:1 with the
application so the form maps cleanly onto storage and onto the derived
``FeatureSet``:

    LoanApplication
      ├─ Business          (industry, state, years in business, revenue, fleet)
      ├─ Guarantor         (FICO, homeowner, derog flags, CDL, experience)   [optional → corp-only]
      ├─ BusinessCredit    (PayNet score, trade lines, comparable credit)
      ├─ LoanRequest       (amount, term, down payment, soft costs, sale type)
      └─ Equipment         (type, year, condition, mileage)
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

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str | None] = mapped_column(String(80), default=None)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|submitted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    business: Mapped["Business"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    guarantor: Mapped["Guarantor | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    business_credit: Mapped["BusinessCredit | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    loan_request: Mapped["LoanRequest"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    equipment: Mapped["Equipment"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    runs: Mapped[list["UnderwritingRun"]] = relationship(  # noqa: F821
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="desc(UnderwritingRun.created_at)",
    )


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), unique=True
    )
    legal_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(2))
    years_in_business: Mapped[float] = mapped_column(Float, default=0.0)
    annual_revenue: Mapped[float | None] = mapped_column(Float, default=None)
    entity_type: Mapped[str | None] = mapped_column(String(40), default=None)
    number_of_trucks: Mapped[int | None] = mapped_column(Integer, default=None)

    application: Mapped["LoanApplication"] = relationship(back_populates="business")


class Guarantor(Base):
    __tablename__ = "guarantors"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), unique=True
    )
    full_name: Mapped[str | None] = mapped_column(String(200), default=None)
    fico: Mapped[int | None] = mapped_column(Integer, default=None)
    is_homeowner: Mapped[bool | None] = mapped_column(Boolean, default=None)
    is_us_citizen: Mapped[bool | None] = mapped_column(Boolean, default=None)
    industry_experience_years: Mapped[float | None] = mapped_column(Float, default=None)
    has_cdl: Mapped[bool | None] = mapped_column(Boolean, default=None)
    cdl_years: Mapped[float | None] = mapped_column(Float, default=None)
    has_secondary_income: Mapped[bool | None] = mapped_column(Boolean, default=None)
    # --- derogatory credit history flags ---
    bankruptcy: Mapped[bool] = mapped_column(Boolean, default=False)
    bankruptcy_years_since_discharge: Mapped[float | None] = mapped_column(Float, default=None)
    has_open_judgments: Mapped[bool] = mapped_column(Boolean, default=False)
    has_foreclosures: Mapped[bool] = mapped_column(Boolean, default=False)
    has_repossessions: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tax_liens: Mapped[bool] = mapped_column(Boolean, default=False)
    has_recent_collections: Mapped[bool] = mapped_column(Boolean, default=False)
    collections_years_ago: Mapped[float | None] = mapped_column(Float, default=None)
    personal_revolving_balance: Mapped[float | None] = mapped_column(Float, default=None)
    unsecured_debt: Mapped[float | None] = mapped_column(Float, default=None)

    application: Mapped["LoanApplication"] = relationship(back_populates="guarantor")


class BusinessCredit(Base):
    __tablename__ = "business_credit"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), unique=True
    )
    paynet_score: Mapped[int | None] = mapped_column(Integer, default=None)
    trade_lines: Mapped[int | None] = mapped_column(Integer, default=None)
    # Comparable prior business borrowing, as a % of the requested amount.
    comparable_credit_pct: Mapped[float | None] = mapped_column(Float, default=None)

    application: Mapped["LoanApplication"] = relationship(back_populates="business_credit")


class LoanRequest(Base):
    __tablename__ = "loan_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), unique=True
    )
    amount: Mapped[float] = mapped_column(Float)
    term_months: Mapped[int] = mapped_column(Integer, default=60)
    down_payment_pct: Mapped[float | None] = mapped_column(Float, default=None)
    soft_costs_pct: Mapped[float | None] = mapped_column(Float, default=None)
    is_private_party_sale: Mapped[bool] = mapped_column(Boolean, default=False)

    application: Mapped["LoanApplication"] = relationship(back_populates="loan_request")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), unique=True
    )
    equipment_type: Mapped[str] = mapped_column(String(60))
    year: Mapped[int | None] = mapped_column(Integer, default=None)
    condition: Mapped[str | None] = mapped_column(String(20), default=None)  # new|used
    mileage: Mapped[int | None] = mapped_column(Integer, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    application: Mapped["LoanApplication"] = relationship(back_populates="equipment")
