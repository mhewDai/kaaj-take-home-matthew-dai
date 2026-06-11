"""Feature derivation: raw application -> normalized FeatureSet.

This is the "derive necessary features" workflow step. It turns stored
application data into the flat, normalized vocabulary the rule evaluators read,
computing derived signals the PDFs care about:

  * equipment_age_years   (current year - equipment.year)
  * is_startup            (years in business < STARTUP_THRESHOLD)
  * is_trucking           (industry in the trucking set)
  * has_personal_guarantee / corp_only
  * has_paynet            (PayNet score present)
"""
from __future__ import annotations

from datetime import datetime

from app.models.application import LoanApplication
from app.models.enums import TRUCKING_INDUSTRIES, Industry
from app.rules.types import FeatureSet

STARTUP_THRESHOLD_YEARS = 2.0


def _current_year() -> int:
    return datetime.now().year


def derive_features(app: LoanApplication, *, reference_year: int | None = None) -> FeatureSet:
    year_now = reference_year or _current_year()
    biz = app.business
    g = app.guarantor
    bc = app.business_credit
    lr = app.loan_request
    eq = app.equipment

    has_pg = g is not None and g.fico is not None
    paynet = bc.paynet_score if bc else None

    industry = biz.industry if biz else None
    is_trucking = industry in {i.value for i in TRUCKING_INDUSTRIES} if industry else False

    equipment_age = None
    if eq and eq.year:
        equipment_age = max(0, year_now - eq.year)

    values: dict = {
        # --- credit ---
        "fico": g.fico if g else None,
        "paynet": paynet,
        "has_paynet": paynet is not None,
        "has_personal_guarantee": has_pg,
        "corp_only": not has_pg,
        # --- business ---
        "industry": industry,
        "state": (biz.state.upper() if biz and biz.state else None),
        "time_in_business_years": biz.years_in_business if biz else None,
        "annual_revenue": biz.annual_revenue if biz else None,
        "trucks_operating": biz.number_of_trucks if biz else None,
        "is_startup": (
            biz.years_in_business < STARTUP_THRESHOLD_YEARS
            if biz and biz.years_in_business is not None
            else None
        ),
        "is_trucking": is_trucking,
        # --- guarantor attributes ---
        "homeownership": g.is_homeowner if g else None,
        "us_citizen": g.is_us_citizen if g else None,
        "industry_experience_years": g.industry_experience_years if g else None,
        "has_cdl": g.has_cdl if g else None,
        "cdl_years": g.cdl_years if g else None,
        "has_secondary_income": g.has_secondary_income if g else None,
        # --- derogatory flags ---
        "bankruptcy": g.bankruptcy if g else False,
        "bankruptcy_years_since_discharge": g.bankruptcy_years_since_discharge if g else None,
        "has_open_judgments": g.has_open_judgments if g else False,
        "has_foreclosures": g.has_foreclosures if g else False,
        "has_repossessions": g.has_repossessions if g else False,
        "has_tax_liens": g.has_tax_liens if g else False,
        "has_recent_collections": g.has_recent_collections if g else False,
        "collections_years_ago": g.collections_years_ago if g else None,
        "personal_revolving_balance": g.personal_revolving_balance if g else None,
        "unsecured_debt": g.unsecured_debt if g else None,
        # --- business credit ---
        "comparable_credit_pct": bc.comparable_credit_pct if bc else None,
        "trade_lines": bc.trade_lines if bc else None,
        # --- loan / equipment ---
        "loan_amount": lr.amount if lr else None,
        "loan_term_months": lr.term_months if lr else None,
        "down_payment_pct": lr.down_payment_pct if lr else None,
        "soft_costs_pct": lr.soft_costs_pct if lr else None,
        "is_private_party_sale": lr.is_private_party_sale if lr else False,
        "equipment_type": eq.equipment_type if eq else None,
        "equipment_year": eq.year if eq else None,
        "equipment_age_years": equipment_age,
        "equipment_condition": eq.condition if eq else None,
        "equipment_mileage": eq.mileage if eq else None,
    }
    return FeatureSet(values=values)


def validate_completeness(app: LoanApplication) -> list[str]:
    """Workflow step 1: ensure the application has the minimum required data.

    Returns a list of human-readable problems (empty == valid). We require enough
    to make a meaningful matching decision; optional credit flags default to
    "clean" and missing soft data degrades to warnings inside the rules.
    """
    problems: list[str] = []
    if app.business is None:
        problems.append("Business information is missing.")
    else:
        if not app.business.legal_name:
            problems.append("Business legal name is required.")
        if not app.business.industry:
            problems.append("Business industry is required.")
        if not app.business.state:
            problems.append("Business state is required.")
        if app.business.years_in_business is None:
            problems.append("Years in business is required.")
    if app.loan_request is None or app.loan_request.amount is None:
        problems.append("Loan amount is required.")
    elif app.loan_request.amount <= 0:
        problems.append("Loan amount must be positive.")
    if app.equipment is None or not app.equipment.equipment_type:
        problems.append("Equipment type is required.")
    # Need at least one credit signal to underwrite (guarantor FICO or PayNet).
    has_fico = app.guarantor is not None and app.guarantor.fico is not None
    has_paynet = app.business_credit is not None and app.business_credit.paynet_score is not None
    if not has_fico and not has_paynet:
        problems.append(
            "At least one credit score is required: guarantor FICO or business PayNet."
        )
    return problems
