"""Scenario tests for the matching engine against the real seeded policies.

These are the "critical matching logic" tests: each one crafts an applicant and
asserts the eligibility decision / chosen program / rejection reason for a
specific lender, exercising the actual policy data seeded from the PDFs.
"""
from __future__ import annotations

import pytest

from app.matching import build_lender_policy, evaluate_lender
from app.models.lender import Lender
from app.rules.types import FeatureSet


def make_features(**over) -> FeatureSet:
    base = dict(
        fico=730, paynet=690, has_paynet=True, has_personal_guarantee=True, corp_only=False,
        industry="construction", state="TX", time_in_business_years=6, annual_revenue=1_000_000,
        is_startup=False, is_trucking=False, trucks_operating=None,
        homeownership=True, us_citizen=True, industry_experience_years=8,
        has_cdl=None, cdl_years=None, has_secondary_income=True,
        bankruptcy=False, bankruptcy_years_since_discharge=None,
        has_open_judgments=False, has_foreclosures=False, has_repossessions=False,
        has_tax_liens=False, has_recent_collections=False, collections_years_ago=None,
        personal_revolving_balance=10000, unsecured_debt=5000,
        comparable_credit_pct=80, trade_lines=5,
        loan_amount=120000, loan_term_months=60, down_payment_pct=15, soft_costs_pct=10,
        is_private_party_sale=False,
        equipment_type="construction_equipment", equipment_year=2022,
        equipment_age_years=3, equipment_condition="used", equipment_mileage=None,
    )
    base.update(over)
    if "paynet" in over and "has_paynet" not in over:
        base["has_paynet"] = over["paynet"] is not None
    if "has_personal_guarantee" in over and "corp_only" not in over:
        base["corp_only"] = not over["has_personal_guarantee"]
    return FeatureSet(values=base)


@pytest.fixture
def get_policy(db):
    def _get(slug):
        lender = db.query(Lender).filter(Lender.slug == slug).first()
        assert lender is not None, f"lender {slug} not seeded"
        return build_lender_policy(lender)

    return _get


# --- Stearns ----------------------------------------------------------------
def test_stearns_tier1_strong_applicant(get_policy):
    ev = evaluate_lender(get_policy("stearns-bank"),
                         make_features(fico=730, paynet=690, time_in_business_years=4))
    assert ev.eligible
    assert ev.best_program.program_name == "Standard Tier 1"


def test_stearns_tier3_when_only_tier3_thresholds_met(get_policy):
    ev = evaluate_lender(get_policy("stearns-bank"),
                         make_features(fico=702, paynet=666, time_in_business_years=2))
    assert ev.eligible
    assert ev.best_program.program_name == "Standard Tier 3"


def test_stearns_corp_only_path(get_policy):
    ev = evaluate_lender(
        get_policy("stearns-bank"),
        make_features(has_personal_guarantee=False, fico=None, paynet=705,
                      time_in_business_years=12),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "Corp-Only Tier 1"


def test_stearns_excluded_industry_knocks_out(get_policy):
    ev = evaluate_lender(get_policy("stearns-bank"), make_features(industry="restaurants"))
    assert not ev.eligible
    assert any("excluded" in r.lower() for r in ev.reasons)


def test_stearns_recent_bankruptcy_knocks_out(get_policy):
    ev = evaluate_lender(
        get_policy("stearns-bank"),
        make_features(bankruptcy=True, bankruptcy_years_since_discharge=3),
    )
    assert not ev.eligible


def test_stearns_high_revolving_debt_knocks_out(get_policy):
    ev = evaluate_lender(
        get_policy("stearns-bank"),
        make_features(personal_revolving_balance=45000),
    )
    assert not ev.eligible


# --- Apex -------------------------------------------------------------------
def test_apex_excluded_state(get_policy):
    ev = evaluate_lender(get_policy("apex-commercial-capital"), make_features(state="CA"))
    assert not ev.eligible
    assert any("CA" in r for r in ev.reasons)


def test_apex_aplus_for_eligible_industry(get_policy):
    ev = evaluate_lender(
        get_policy("apex-commercial-capital"),
        make_features(industry="construction", fico=730, paynet=675,
                      time_in_business_years=6, loan_amount=150000, equipment_age_years=3),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "A+ (Standard)"


def test_apex_falls_to_general_a_when_not_in_aplus_whitelist(get_policy):
    # wholesale isn't in the A+ eligible-industry list, but the general A program
    # has no whitelist -> applicant should match A, not A+.
    ev = evaluate_lender(
        get_policy("apex-commercial-capital"),
        make_features(industry="wholesale", fico=730, paynet=675,
                      time_in_business_years=6, loan_amount=150000),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "A (Standard)"


def test_apex_corp_only_requires_revenue(get_policy):
    ev = evaluate_lender(
        get_policy("apex-commercial-capital"),
        make_features(has_personal_guarantee=False, fico=None, paynet=None,
                      time_in_business_years=6, annual_revenue=1_000_000,
                      comparable_credit_pct=80),
    )
    # $1MM revenue < $3MM corp-only requirement -> not eligible
    assert not ev.eligible


# --- Advantage+ -------------------------------------------------------------
def test_advantage_rejects_trucking(get_policy):
    ev = evaluate_lender(
        get_policy("advantage-plus-financing"),
        make_features(industry="trucking_long_haul", is_trucking=True, loan_amount=50000),
    )
    assert not ev.eligible
    assert any("trucking" in r.lower() for r in ev.reasons)


def test_advantage_rejects_over_cap(get_policy):
    ev = evaluate_lender(
        get_policy("advantage-plus-financing"),
        make_features(loan_amount=120000, is_trucking=False, industry="construction"),
    )
    assert not ev.eligible


def test_advantage_eligible_small_non_trucking(get_policy):
    ev = evaluate_lender(
        get_policy("advantage-plus-financing"),
        make_features(loan_amount=50000, fico=690, industry="construction",
                      is_trucking=False, down_payment_pct=10),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "Standard (Established)"


def test_advantage_startup_needs_higher_fico(get_policy):
    base = dict(loan_amount=40000, is_trucking=False, industry="construction",
                is_startup=True, time_in_business_years=1, down_payment_pct=25)
    assert not evaluate_lender(get_policy("advantage-plus-financing"),
                               make_features(fico=685, **base)).eligible
    assert evaluate_lender(get_policy("advantage-plus-financing"),
                           make_features(fico=710, **base)).eligible


# --- Citizens ---------------------------------------------------------------
def test_citizens_tier1_homeowner(get_policy):
    ev = evaluate_lender(
        get_policy("citizens-bank"),
        make_features(loan_amount=60000, homeownership=True, fico=710,
                      time_in_business_years=3, us_citizen=True),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "Tier 1 — General ($75K)"


def test_citizens_non_homeowner_path(get_policy):
    ev = evaluate_lender(
        get_policy("citizens-bank"),
        make_features(loan_amount=45000, homeownership=False, fico=710,
                      time_in_business_years=3, us_citizen=True),
    )
    assert ev.eligible
    assert ev.best_program.program_name == "Tier 2 — Non-Homeowner ($50K)"


def test_citizens_california_excluded(get_policy):
    ev = evaluate_lender(get_policy("citizens-bank"),
                         make_features(state="CA", loan_amount=60000))
    assert not ev.eligible


# --- Falcon -----------------------------------------------------------------
def test_falcon_trucking_program(get_policy):
    ev = evaluate_lender(
        get_policy("falcon-equipment-finance"),
        make_features(industry="trucking_long_haul", is_trucking=True,
                      trucks_operating=6, time_in_business_years=6,
                      fico=705, paynet=685, loan_amount=120000,
                      equipment_type="class_8_truck", equipment_age_years=4),
    )
    assert ev.eligible
    assert "Trucking" in ev.best_program.program_name


def test_falcon_below_min_fico_knocks_out(get_policy):
    ev = evaluate_lender(get_policy("falcon-equipment-finance"),
                         make_features(fico=650))
    assert not ev.eligible


def test_falcon_manufacturing_high_cap(get_policy):
    # Manufacturing app-only goes to $350k; commercial only to $250k.
    ev = evaluate_lender(
        get_policy("falcon-equipment-finance"),
        make_features(industry="manufacturing", loan_amount=300000,
                      equipment_type="machine_tools"),
    )
    assert ev.eligible
    assert "Manufacturing" in ev.best_program.program_name


# --- scoring ----------------------------------------------------------------
def test_eligible_outranks_ineligible_score(get_policy):
    strong = evaluate_lender(get_policy("falcon-equipment-finance"), make_features())
    weak = evaluate_lender(get_policy("advantage-plus-financing"),
                           make_features(loan_amount=120000))
    assert strong.eligible and strong.fit_score >= 60
    assert not weak.eligible and weak.fit_score <= 55
