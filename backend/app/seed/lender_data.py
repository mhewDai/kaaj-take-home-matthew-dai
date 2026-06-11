"""Normalized policy data for the five seed lenders.

Each lender's PDF is encoded here as declarative rules using the rule registry.
This file *is* the "parse PDF -> normalized policy" output: a human read each
guideline once and expressed it as data. New lenders are added by appending a
dict here (or via the API/UI) — no engine code changes.

Helper builders keep the intent readable:
  ko(...)     -> lender-wide knockout rule (applies to every program)
  qual(...)   -> program qualification rule (gates approval)
  prereq(...) -> program applicability gate (selects which tier applies)
  pref(...)   -> soft preference (never blocks; affects warnings/score)

Notable modeling choices (see DECISIONS.md for the full list):
  * Personal credit score is unified as ``fico`` even where a lender names a
    specific bureau (Citizens -> TransUnion, Advantage+ -> Equifax FICO v5).
  * "Does not finance bankruptcies" is encoded as a very large seasoning window.
  * Citizens' detailed equipment-age->term matrices are simplified to a global
    max term; the per-equipment matrix is noted as future work.
"""
from __future__ import annotations

from typing import Any

from app.models.enums import EquipmentType, Industry, RuleSeverity


def _rule(rule_type: str, severity: RuleSeverity, **config: Any) -> dict:
    return {"rule_type": rule_type, "severity": severity.value, "config": config}


def ko(rule_type: str, **config: Any) -> dict:
    return _rule(rule_type, RuleSeverity.KNOCKOUT, **config)


def qual(rule_type: str, **config: Any) -> dict:
    return _rule(rule_type, RuleSeverity.QUALIFICATION, **config)


def prereq(rule_type: str, **config: Any) -> dict:
    return _rule(rule_type, RuleSeverity.PREREQUISITE, **config)


def pref(rule_type: str, **config: Any) -> dict:
    return _rule(rule_type, RuleSeverity.PREFERENCE, **config)


I = Industry  # noqa: E741 - terse alias for readability of the data below
E = EquipmentType


# =========================================================================== #
# 1. STEARNS BANK — Equipment Finance Credit Box
# =========================================================================== #
STEARNS = {
    "name": "Stearns Bank",
    "slug": "stearns-bank",
    "description": "Equipment Finance Credit Box (tiered FICO/PayNet/TIB).",
    "metadata_json": {"source": "EF Credit Box 4.14.2025.pdf", "member_fdic": True},
    "rules": [  # lender-wide knockouts
        ko("no_bankruptcy_within_years", years=7),
        ko("max_personal_revolving", max_revolving=30000,
           max_revolving_plus_unsecured=50000, on_missing="warn"),
        ko("excluded_industries", industries=[
            I.GAMING_GAMBLING, I.HAZMAT, I.OIL_GAS_PETROLEUM, I.MSB,
            I.ADULT_ENTERTAINMENT, I.WEAPONS_FIREARMS, I.BEAUTY_TANNING_SALON,
            I.TATTOO_PIERCING, I.AESTHETIC, I.REAL_ESTATE, I.TRUCKING_LONG_HAUL,
            I.RESTAURANTS, I.CAR_WASH,
        ]),
    ],
    "programs": [
        # --- Standard credit box: requires personal guarantor + PayNet ---
        {"name": "Standard Tier 1", "rank": 1,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_paynet_present"),
                   qual("min_fico", min=725), qual("min_paynet", min=685),
                   qual("min_time_in_business", min_years=3)]},
        {"name": "Standard Tier 2", "rank": 2,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_paynet_present"),
                   qual("min_fico", min=710), qual("min_paynet", min=675),
                   qual("min_time_in_business", min_years=3)]},
        {"name": "Standard Tier 3", "rank": 3,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_paynet_present"),
                   qual("min_fico", min=700), qual("min_paynet", min=665),
                   qual("min_time_in_business", min_years=2)]},
        # --- No PayNet: requires PG, PayNet absent (higher FICO) ---
        {"name": "No-PayNet Tier 1", "rank": 1,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_no_paynet"),
                   qual("min_fico", min=735), qual("min_time_in_business", min_years=5)]},
        {"name": "No-PayNet Tier 2", "rank": 2,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_no_paynet"),
                   qual("min_fico", min=720), qual("min_time_in_business", min_years=3)]},
        {"name": "No-PayNet Tier 3", "rank": 3,
         "rules": [prereq("requires_personal_guarantee_present"),
                   prereq("requires_no_paynet"),
                   qual("min_fico", min=710), qual("min_time_in_business", min_years=2)]},
        # --- Corp only: no personal guarantor (PayNet-based) ---
        {"name": "Corp-Only Tier 1", "rank": 1,
         "rules": [prereq("requires_corp_only"),
                   qual("min_paynet", min=700), qual("min_time_in_business", min_years=10)]},
        {"name": "Corp-Only Tier 2", "rank": 2,
         "rules": [prereq("requires_corp_only"),
                   qual("min_paynet", min=690), qual("min_time_in_business", min_years=5)]},
        {"name": "Corp-Only Tier 3", "rank": 3,
         "rules": [prereq("requires_corp_only"),
                   qual("min_paynet", min=680), qual("min_time_in_business", min_years=5)]},
    ],
}


# =========================================================================== #
# 2. APEX COMMERCIAL CAPITAL — Broker rate grades
# =========================================================================== #
_APEX_ELIGIBLE_APLUS = [
    I.ARBOR_LANDSCAPING, I.AUTOMOTIVE_REPAIR, I.CONSTRUCTION, I.COMMERCIAL_CLEANING,
    I.MANUFACTURING, I.MACHINE_TOOLS, I.WASTE_MANAGEMENT, I.MEDICAL_DENTAL_VET,
]
APEX = {
    "name": "Apex Commercial Capital",
    "slug": "apex-commercial-capital",
    "description": "Equipment Finance broker rate table (A+/A/B/C, Medical, Corp-only).",
    "metadata_json": {"source": "Apex EF Broker Guidelines_082725.pdf",
                      "effective": "2025-08-21"},
    "rules": [
        ko("excluded_states", states=["CA", "NV", "ND", "VT"]),
        ko("excluded_industries", industries=[
            I.CANNABIS, I.GAMING_GAMBLING, I.CHURCH_NONPROFIT, I.OIL_GAS_PETROLEUM,
            I.NAIL_SALON, I.BEAUTY_TANNING_SALON, I.TRUCKING_LOCAL,
            I.TRUCKING_LONG_HAUL, I.LOGGING,
        ]),
        ko("excluded_equipment_types", types=[
            E.AIRCRAFT_BOAT, E.ATM, E.AUDIO_VISUAL, E.COPIER, E.ELECTRIC_VEHICLE,
            E.FURNITURE, E.KIOSK, E.SIGNAGE, E.TANNING_BED, E.LOGGING_EQUIPMENT,
        ]),
        ko("max_equipment_age", max_years=15, on_missing="warn"),
        ko("no_private_party_sale", on_missing="pass"),
        ko("max_soft_costs_pct", max_pct=25, on_missing="pass"),
        # Comparable business borrowing requirement (amount-tiered).
        qual("min_comparable_credit_pct", on_missing="warn", tiers=[
            {"min": 50000, "max": 100000, "pct": 50},
            {"min": 100000, "max": None, "pct": 75},
        ]),
    ],
    "programs": [
        {"name": "A+ (Standard)", "rank": 1, "rate": 6.5, "credit_grade": "A+",
         "metadata_json": {"app_only_max": 200000, "max_collateral_age": 5},
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("min_time_in_business", min_years=5), qual("min_fico", min=720),
                   qual("min_paynet", min=670), qual("loan_amount_range", min=10000, max=500000),
                   qual("allowed_industries", industries=_APEX_ELIGIBLE_APLUS),
                   qual("max_equipment_age", max_years=5, on_missing="warn"),
                   qual("no_private_party_sale", on_missing="pass")]},
        {"name": "A (Standard)", "rank": 2, "rate": 7.25, "credit_grade": "A",
         "metadata_json": {"app_only_max": 200000},
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("min_time_in_business", min_years=5), qual("min_fico", min=700),
                   qual("min_paynet", min=660), qual("loan_amount_range", min=10000, max=500000)]},
        {"name": "Medical A", "rank": 2, "rate": 7.0, "credit_grade": "A",
         "metadata_json": {"requires_active_license": True, "app_only_max": 200000},
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("allowed_industries", industries=[I.MEDICAL_DENTAL_VET, I.HEALTHCARE]),
                   qual("min_time_in_business", min_years=5), qual("min_fico", min=700),
                   qual("loan_amount_range", min=10000, max=500000)]},
        {"name": "B (Standard)", "rank": 3, "rate": 8.25, "credit_grade": "B",
         "metadata_json": {"app_only_max": 100000},
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("min_time_in_business", min_years=3), qual("min_fico", min=670),
                   qual("min_paynet", min=650), qual("loan_amount_range", min=10000, max=250000)]},
        {"name": "Medical B", "rank": 3, "rate": 7.5, "credit_grade": "B",
         "metadata_json": {"requires_active_license": True, "app_only_max": 100000},
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("allowed_industries", industries=[I.MEDICAL_DENTAL_VET, I.HEALTHCARE]),
                   qual("min_time_in_business", min_years=2), qual("min_fico", min=670),
                   qual("loan_amount_range", min=10000, max=250000)]},
        {"name": "C (Standard)", "rank": 4, "rate": 11.0, "credit_grade": "C",
         "rules": [prereq("requires_personal_guarantee_present"),
                   qual("min_time_in_business", min_years=2), qual("min_fico", min=640),
                   qual("min_paynet", min=640), qual("loan_amount_range", min=10000, max=100000)]},
        {"name": "Corp Only (7.00% Buy Rate)", "rank": 1, "rate": 7.0,
         "metadata_json": {"requires_financials": True},
         "rules": [prereq("requires_corp_only"),
                   qual("min_time_in_business", min_years=5),
                   qual("min_annual_revenue", min=3000000),
                   qual("min_comparable_credit_pct", min_pct=75, on_missing="warn")]},
    ],
}


# =========================================================================== #
# 3. ADVANTAGE+ FINANCING — ICP Broker $75K (non-trucking)
# =========================================================================== #
ADVANTAGE = {
    "name": "Advantage+ Financing",
    "slug": "advantage-plus-financing",
    "description": "Broker ICP for non-trucking applications up to $75,000.",
    "metadata_json": {"source": "Advantage++Broker+2025.pdf", "max_single_app": 75000},
    "rules": [
        ko("requires_us_citizen"),
        ko("non_trucking_only"),
        # "Do you finance bankruptcies? No" -> reject any bankruptcy (huge window).
        ko("no_bankruptcy_within_years", years=100),
        ko("no_open_judgments"),
        ko("no_foreclosures"),
        ko("no_repossessions"),
        ko("no_tax_liens"),
        ko("no_recent_collections", years=3),
    ],
    "programs": [
        {"name": "Standard (Established)", "rank": 1,
         "metadata_json": {"credit_range": "A to B-", "fico_bureau": "Equifax FICO v5"},
         "rules": [prereq("requires_established"),
                   qual("min_fico", min=680),
                   qual("min_industry_experience", min_years=3),
                   qual("loan_amount_range", min=10000, max=75000),
                   qual("max_loan_term", max_months=60),
                   qual("min_down_payment_pct", min_pct=10, on_missing="warn"),
                   pref("prefers_secondary_income")]},
        {"name": "Start-Up", "rank": 2,
         "metadata_json": {"note": "700+ FICO and additional 10% security deposit"},
         "rules": [prereq("requires_startup"),
                   qual("min_fico", min=700),
                   qual("min_industry_experience", min_years=3),
                   qual("loan_amount_range", min=10000, max=75000),
                   qual("max_loan_term", max_months=60),
                   qual("min_down_payment_pct", min_pct=20, on_missing="warn"),
                   pref("prefers_secondary_income")]},
    ],
}


# =========================================================================== #
# 4. CITIZENS BANK — 2025 Equipment Finance Program
# =========================================================================== #
CITIZENS = {
    "name": "Citizens Bank",
    "slug": "citizens-bank",
    "description": "2025 Equipment Finance Program (application-only tiers).",
    "metadata_json": {"source": "2025 Program Guidelines UPDATED.pdf",
                      "note": "Equipment-age->term matrices simplified to a global max term."},
    "rules": [
        ko("excluded_states", states=["CA"]),
        ko("excluded_industries", industries=[I.CANNABIS]),
        ko("requires_us_citizen"),
        ko("no_bankruptcy_within_years", years=5),
        ko("max_loan_term", max_months=60),
    ],
    "programs": [
        {"name": "Tier 1 — General ($75K)", "rank": 1,
         "metadata_json": {"all_in_max": 75000, "credit_bureau": "TransUnion",
                          "max_points": 10},
         "rules": [prereq("requires_established"),
                   qual("min_time_in_business", min_years=2), qual("min_fico", min=700),
                   qual("requires_homeownership"),
                   qual("loan_amount_range", min=10000, max=75000)]},
        {"name": "Tier 2 — Start-Up ($50K)", "rank": 2,
         "metadata_json": {"all_in_max": 50000, "max_points": 7},
         "rules": [prereq("requires_startup"),
                   qual("min_fico", min=700), qual("requires_homeownership"),
                   qual("min_industry_experience", min_years=5),
                   qual("loan_amount_range", min=10000, max=50000)]},
        {"name": "Tier 2 — Non-Homeowner ($50K)", "rank": 3,
         "metadata_json": {"all_in_max": 50000, "note": "5 years at current residence"},
         "rules": [qual("min_fico", min=700),
                   qual("min_time_in_business", min_years=2),
                   qual("loan_amount_range", min=10000, max=50000)]},
        {"name": "Tier 3 — Full Financials ($75K–$1M)", "rank": 4,
         "metadata_json": {"requires_full_financials": True},
         "rules": [qual("min_fico", min=700),
                   qual("min_time_in_business", min_years=2),
                   qual("loan_amount_range", min=75000, max=1000000)]},
    ],
}


# =========================================================================== #
# 5. FALCON EQUIPMENT FINANCE — Rates & Programs
# =========================================================================== #
FALCON = {
    "name": "Falcon Equipment Finance",
    "slug": "falcon-equipment-finance",
    "description": "Rates & Programs (A–E grades; app-only caps by industry).",
    "metadata_json": {"source": "112025 Rates - STANDARD.pdf", "member_fdic": True},
    "rules": [  # base credit guidelines apply to every program
        qual("min_time_in_business", min_years=3),
        qual("min_fico", min=680),
        qual("min_paynet", min=660),
        qual("min_comparable_credit_pct", min_pct=70, on_missing="warn"),
        ko("no_bankruptcy_within_years", years=15),
    ],
    "programs": [
        {"name": "Manufacturing App-Only ($350K)", "rank": 1, "credit_grade": "A",
         "metadata_json": {"app_only_max": 350000},
         "rules": [qual("allowed_industries",
                        industries=[I.MANUFACTURING, I.MACHINE_TOOLS, I.WOODWORKING]),
                   qual("loan_amount_range", min=15000, max=350000)]},
        {"name": "Commercial App-Only ($250K)", "rank": 2, "credit_grade": "A",
         "metadata_json": {"app_only_max": 250000},
         "rules": [qual("non_trucking_only"),
                   qual("loan_amount_range", min=15000, max=250000)]},
        {"name": "Trucking / Logging App-Only ($150K, A/B only)", "rank": 1,
         "credit_grade": "B",
         "metadata_json": {"app_only_max": 150000, "note": "A/B credits only"},
         "rules": [prereq("requires_trucking"),
                   qual("min_trucks_operating", min=5),
                   qual("min_time_in_business", min_years=5),
                   qual("min_fico", min=700), qual("min_paynet", min=680),
                   qual("max_equipment_age", max_years=10, on_missing="warn"),
                   qual("loan_amount_range", min=15000, max=150000)]},
    ],
}


ALL_LENDERS = [STEARNS, APEX, ADVANTAGE, CITIZENS, FALCON]
