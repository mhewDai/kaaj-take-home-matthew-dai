"""Pydantic schemas for underwriting runs and match results."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CriterionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program_id: int | None = None
    program_name: str | None = None
    rule_type: str
    label: str
    status: str
    severity: str
    message: str
    expected: str | None = None
    actual: str | None = None


class MatchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lender_id: int
    lender_name: str
    eligible: bool
    fit_score: float
    rank: int
    matched_program_id: int | None = None
    matched_program_name: str | None = None
    matched_program_rate: float | None = None
    reasons: list[str] = Field(default_factory=list)
    criteria: list[CriterionResultRead] = Field(default_factory=list)


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    status: str
    error: str | None = None
    eligible_count: int
    lender_count: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunRead(RunSummary):
    derived_features: dict[str, Any] = Field(default_factory=dict)
    results: list[MatchResultRead] = Field(default_factory=list)
