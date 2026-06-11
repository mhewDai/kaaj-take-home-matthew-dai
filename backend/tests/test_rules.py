"""Unit tests for individual rule evaluators (pure, no DB)."""
from __future__ import annotations

from app.models.enums import EvalStatus
from app.rules import registry
from app.rules.types import FeatureSet


def fs(**values) -> FeatureSet:
    return FeatureSet(values=values)


def ev(rule_type, config, **values):
    return registry.evaluate(rule_type, config, fs(**values))


# --- numeric minimums --------------------------------------------------------
def test_min_fico_pass_and_margin():
    r = ev("min_fico", {"min": 700}, fico=760)
    assert r.status == EvalStatus.PASS
    assert r.margin is not None and 0 < r.margin <= 1
    assert r.expected == "≥ 700"


def test_min_fico_fail_message_matches_brief_example():
    # The brief's example: "minimum required score is 700 but the borrower's is 600".
    r = ev("min_fico", {"min": 700}, fico=600)
    assert r.status == EvalStatus.FAIL
    assert "700" in r.message and "600" in r.message


def test_min_fico_missing_is_insufficient_data_by_default():
    r = ev("min_fico", {"min": 700})
    assert r.status == EvalStatus.INSUFFICIENT_DATA


def test_on_missing_warn_downgrades_to_warning():
    r = ev("min_fico", {"min": 700, "on_missing": "warn"})
    assert r.status == EvalStatus.WARNING


# --- loan amount range -------------------------------------------------------
def test_loan_amount_below_min_fails():
    r = ev("loan_amount_range", {"min": 10000, "max": 75000}, loan_amount=5000)
    assert r.status == EvalStatus.FAIL
    assert "below" in r.message


def test_loan_amount_above_max_fails():
    r = ev("loan_amount_range", {"min": 10000, "max": 75000}, loan_amount=120000)
    assert r.status == EvalStatus.FAIL
    assert "exceeds" in r.message


def test_loan_amount_within_range_passes():
    r = ev("loan_amount_range", {"min": 10000, "max": 75000}, loan_amount=40000)
    assert r.status == EvalStatus.PASS


# --- exclusions --------------------------------------------------------------
def test_excluded_industries_blocks_listed_industry():
    r = ev("excluded_industries", {"industries": ["restaurants"]}, industry="restaurants")
    assert r.status == EvalStatus.FAIL


def test_excluded_industries_allows_other_industry():
    r = ev("excluded_industries", {"industries": ["restaurants"]}, industry="construction")
    assert r.status == EvalStatus.PASS


def test_excluded_states_is_case_insensitive():
    r = ev("excluded_states", {"states": ["CA", "NV"]}, state="ca")
    assert r.status == EvalStatus.FAIL


def test_allowed_industries_whitelist_rejects_outsiders():
    r = ev("allowed_industries", {"industries": ["medical_dental_vet"]}, industry="construction")
    assert r.status == EvalStatus.FAIL


# --- derogatory credit -------------------------------------------------------
def test_bankruptcy_within_window_fails():
    r = ev("no_bankruptcy_within_years", {"years": 7},
           bankruptcy=True, bankruptcy_years_since_discharge=3)
    assert r.status == EvalStatus.FAIL


def test_bankruptcy_outside_window_passes():
    r = ev("no_bankruptcy_within_years", {"years": 7},
           bankruptcy=True, bankruptcy_years_since_discharge=9)
    assert r.status == EvalStatus.PASS


def test_no_bankruptcy_reported_passes():
    r = ev("no_bankruptcy_within_years", {"years": 7}, bankruptcy=False)
    assert r.status == EvalStatus.PASS


def test_tax_lien_flag_blocks():
    assert ev("no_tax_liens", {}, has_tax_liens=True).status == EvalStatus.FAIL
    assert ev("no_tax_liens", {}, has_tax_liens=False).status == EvalStatus.PASS


# --- revolving debt knockout (Stearns) --------------------------------------
def test_revolving_over_limit_fails():
    r = ev("max_personal_revolving", {"max_revolving": 30000}, personal_revolving_balance=40000)
    assert r.status == EvalStatus.FAIL


def test_revolving_plus_unsecured_combined_limit():
    r = ev("max_personal_revolving",
           {"max_revolving": 30000, "max_revolving_plus_unsecured": 50000},
           personal_revolving_balance=25000, unsecured_debt=30000)
    assert r.status == EvalStatus.FAIL  # 55k combined > 50k


# --- comparable credit tiers (Apex) -----------------------------------------
def test_comparable_credit_tier_selection():
    # >$100k requires 75%
    r = ev("min_comparable_credit_pct",
           {"tiers": [{"min": 50000, "max": 100000, "pct": 50},
                      {"min": 100000, "max": None, "pct": 75}]},
           loan_amount=150000, comparable_credit_pct=60)
    assert r.status == EvalStatus.FAIL  # 60% < required 75%


def test_comparable_credit_missing_warns():
    r = ev("min_comparable_credit_pct", {"min_pct": 70, "on_missing": "warn"},
           loan_amount=80000)
    assert r.status == EvalStatus.WARNING


# --- equipment age -----------------------------------------------------------
def test_equipment_age_over_max_fails():
    r = ev("max_equipment_age", {"max_years": 5}, equipment_age_years=8)
    assert r.status == EvalStatus.FAIL


# --- prerequisites produce NOT_APPLICABLE -----------------------------------
def test_corp_only_prereq_not_applicable_when_guarantor_present():
    r = ev("requires_corp_only", {}, corp_only=False)
    assert r.status == EvalStatus.NOT_APPLICABLE


def test_corp_only_prereq_applies_when_no_guarantor():
    r = ev("requires_corp_only", {}, corp_only=True)
    assert r.status == EvalStatus.PASS
