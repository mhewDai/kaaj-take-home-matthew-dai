"""Pydantic schemas for lenders, programs and policy rules."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RuleScope, RuleSeverity


class PolicyRuleBase(BaseModel):
    rule_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    severity: RuleSeverity = RuleSeverity.QUALIFICATION
    description: str | None = None
    is_active: bool = True


class PolicyRuleCreate(PolicyRuleBase):
    # When attaching directly to a lender (knockout) leave program_id null.
    program_id: int | None = None


class PolicyRuleUpdate(BaseModel):
    rule_type: str | None = None
    config: dict[str, Any] | None = None
    severity: RuleSeverity | None = None
    description: str | None = None
    is_active: bool | None = None


class PolicyRuleRead(PolicyRuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lender_id: int
    program_id: int | None = None
    scope: str = RuleScope.PROGRAM.value


class ProgramBase(BaseModel):
    name: str
    rank: int = 1
    rate: float | None = None
    credit_grade: str | None = None
    notes: str | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProgramCreate(ProgramBase):
    rules: list[PolicyRuleCreate] = Field(default_factory=list)


class ProgramUpdate(BaseModel):
    name: str | None = None
    rank: int | None = None
    rate: float | None = None
    credit_grade: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class ProgramRead(ProgramBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lender_id: int
    rules: list[PolicyRuleRead] = Field(default_factory=list)


class LenderBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class LenderCreate(LenderBase):
    programs: list[ProgramCreate] = Field(default_factory=list)
    # Lender-wide knockout rules (program_id implicitly null).
    rules: list[PolicyRuleCreate] = Field(default_factory=list)


class LenderUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    is_active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class LenderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: str | None = None
    is_active: bool
    program_count: int = 0


class LenderRead(LenderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    programs: list[ProgramRead] = Field(default_factory=list)
    rules: list[PolicyRuleRead] = Field(default_factory=list)


# --- rule-type registry descriptor (drives the policy editor UI) ---
class RuleParamRead(BaseModel):
    name: str
    type: str
    label: str
    required: bool
    options_enum: str | None = None
    help: str | None = None


class RuleTypeRead(BaseModel):
    key: str
    label: str
    category: str
    description: str
    default_severity: str
    params: list[RuleParamRead]
