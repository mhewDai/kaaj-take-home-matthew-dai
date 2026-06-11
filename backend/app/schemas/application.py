"""Pydantic schemas for loan applications (nested aggregate)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EquipmentCondition, EquipmentType, Industry


class BusinessIn(BaseModel):
    legal_name: str
    industry: Industry
    state: str = Field(min_length=2, max_length=2)
    years_in_business: float = Field(ge=0)
    annual_revenue: float | None = Field(default=None, ge=0)
    entity_type: str | None = None
    number_of_trucks: int | None = Field(default=None, ge=0)


class GuarantorIn(BaseModel):
    full_name: str | None = None
    fico: int | None = Field(default=None, ge=300, le=900)
    is_homeowner: bool | None = None
    is_us_citizen: bool | None = None
    industry_experience_years: float | None = Field(default=None, ge=0)
    has_cdl: bool | None = None
    cdl_years: float | None = Field(default=None, ge=0)
    has_secondary_income: bool | None = None
    bankruptcy: bool = False
    bankruptcy_years_since_discharge: float | None = Field(default=None, ge=0)
    has_open_judgments: bool = False
    has_foreclosures: bool = False
    has_repossessions: bool = False
    has_tax_liens: bool = False
    has_recent_collections: bool = False
    collections_years_ago: float | None = Field(default=None, ge=0)
    personal_revolving_balance: float | None = Field(default=None, ge=0)
    unsecured_debt: float | None = Field(default=None, ge=0)


class BusinessCreditIn(BaseModel):
    paynet_score: int | None = Field(default=None, ge=300, le=900)
    trade_lines: int | None = Field(default=None, ge=0)
    comparable_credit_pct: float | None = Field(default=None, ge=0)


class LoanRequestIn(BaseModel):
    amount: float = Field(gt=0)
    term_months: int = Field(default=60, gt=0, le=120)
    down_payment_pct: float | None = Field(default=None, ge=0, le=100)
    soft_costs_pct: float | None = Field(default=None, ge=0, le=100)
    is_private_party_sale: bool = False


class EquipmentIn(BaseModel):
    equipment_type: EquipmentType
    year: int | None = Field(default=None, ge=1950, le=2100)
    condition: EquipmentCondition | None = None
    mileage: int | None = Field(default=None, ge=0)
    description: str | None = None


class ApplicationCreate(BaseModel):
    reference: str | None = None
    business: BusinessIn
    guarantor: GuarantorIn | None = None
    business_credit: BusinessCreditIn | None = None
    loan_request: LoanRequestIn
    equipment: EquipmentIn


class ApplicationUpdate(BaseModel):
    reference: str | None = None
    business: BusinessIn | None = None
    guarantor: GuarantorIn | None = None
    business_credit: BusinessCreditIn | None = None
    loan_request: LoanRequestIn | None = None
    equipment: EquipmentIn | None = None


# --- read models ---
class BusinessRead(BusinessIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class GuarantorRead(GuarantorIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BusinessCreditRead(BusinessCreditIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class LoanRequestRead(LoanRequestIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EquipmentRead(EquipmentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str | None = None
    status: str
    business: BusinessRead | None = None
    guarantor: GuarantorRead | None = None
    business_credit: BusinessCreditRead | None = None
    loan_request: LoanRequestRead | None = None
    equipment: EquipmentRead | None = None


class ApplicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str | None = None
    status: str
    business_name: str | None = None
    amount: float | None = None
