"""Built-in rule evaluators.

Each function below is one *kind* of policy check. Together they cover every
criterion expressed across the five seed lenders (FICO/PayNet/TIB tiers, loan
caps, industry/state/equipment exclusions, bankruptcy & derog knockouts,
homeownership/CDL/citizenship gates, comparable-credit, soft costs, ...).

Importing this module is what registers the rules — ``app.rules`` does it for
you. To add a new check: write one function, decorate it with ``@rule(...)``.
"""
from __future__ import annotations

from typing import Any

from app.models.enums import EvalStatus, RuleSeverity
from app.rules.registry import Param, rule
from app.rules.types import CriterionResult, FeatureSet

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _missing(
    cfg: dict[str, Any],
    label: str,
    feature_label: str,
) -> CriterionResult:
    """Build a result for the "we don't have this data" case.

    ``on_missing`` lets a policy author decide whether unknown data should block
    (``fail`` — default, a hard credit-box gate), merely warn (``warn`` — a
    documentation/verification item) or pass silently (``pass``).
    """
    mode = cfg.get("on_missing", "fail")
    if mode == "pass":
        status, msg = EvalStatus.PASS, f"{feature_label} not provided — treated as acceptable."
    elif mode == "warn":
        status, msg = (
            EvalStatus.WARNING,
            f"{feature_label} not provided — requires verification.",
        )
    else:
        status, msg = (
            EvalStatus.INSUFFICIENT_DATA,
            f"{feature_label} is required to evaluate this criterion but was not provided.",
        )
    return CriterionResult(rule_type="", label=label, status=status, message=msg)


def _margin(actual: float, threshold: float, band: float) -> float:
    if band <= 0:
        return 1.0
    return max(0.0, min(1.0, (actual - threshold) / band))


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# numeric minimum thresholds (credit scores, TIB, revenue, experience)
# ---------------------------------------------------------------------------


def _min_threshold(
    cfg: dict[str, Any],
    features: FeatureSet,
    *,
    feature: str,
    key: str,
    label: str,
    unit: str = "",
    band: float = 1.0,
    fmt: str = "{:.0f}",
) -> CriterionResult:
    threshold = _num(cfg.get(key))
    actual = _num(features.get(feature))
    if threshold is None:
        return CriterionResult("", label, EvalStatus.PASS, "No minimum configured.")
    if actual is None:
        return _missing(cfg, label, label)
    exp = f"≥ {fmt.format(threshold)}{unit}"
    act = f"{fmt.format(actual)}{unit}"
    if actual >= threshold:
        return CriterionResult(
            "", label, EvalStatus.PASS,
            f"{label} of {act} meets the minimum of {exp[2:]}.",
            expected=exp, actual=act, margin=_margin(actual, threshold, band),
        )
    return CriterionResult(
        "", label, EvalStatus.FAIL,
        f"{label} not met: minimum required is {fmt.format(threshold)}{unit} "
        f"but the application's {label.lower()} is {act}.",
        expected=exp, actual=act,
    )


@rule(
    key="min_fico", label="Minimum FICO", category="credit",
    description="Guarantor personal credit (FICO) must meet the minimum.",
    params=[Param("min", "int", "Minimum FICO"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_fico(cfg, features):
    return _min_threshold(cfg, features, feature="fico", key="min",
                          label="Minimum FICO", band=60)


@rule(
    key="min_paynet", label="Minimum PayNet", category="credit",
    description="Business PayNet MasterScore must meet the minimum.",
    params=[Param("min", "int", "Minimum PayNet"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_paynet(cfg, features):
    return _min_threshold(cfg, features, feature="paynet", key="min",
                          label="Minimum PayNet", band=50)


@rule(
    key="min_time_in_business", label="Minimum time in business", category="business",
    description="Business must have operated for at least N years.",
    params=[Param("min_years", "float", "Minimum years in business"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_time_in_business(cfg, features):
    return _min_threshold(cfg, features, feature="time_in_business_years",
                          key="min_years", label="Time in business",
                          unit=" yrs", band=3, fmt="{:g}")


@rule(
    key="min_annual_revenue", label="Minimum annual revenue", category="business",
    description="Annual business revenue / sales must meet the minimum.",
    params=[Param("min", "float", "Minimum annual revenue ($)"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_annual_revenue(cfg, features):
    return _min_threshold(cfg, features, feature="annual_revenue", key="min",
                          label="Annual revenue", unit="", band=1_000_000,
                          fmt="${:,.0f}")


@rule(
    key="min_industry_experience", label="Minimum industry experience", category="business",
    description="Owner must have N years of experience in the industry.",
    params=[Param("min_years", "float", "Minimum years of experience"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_industry_experience(cfg, features):
    return _min_threshold(cfg, features, feature="industry_experience_years",
                          key="min_years", label="Industry experience",
                          unit=" yrs", band=3, fmt="{:g}")


@rule(
    key="min_trucks_operating", label="Minimum trucks operating", category="business",
    description="Fleet must currently operate at least N trucks.",
    params=[Param("min", "int", "Minimum trucks"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_trucks_operating(cfg, features):
    return _min_threshold(cfg, features, feature="trucks_operating", key="min",
                          label="Trucks operating", unit=" trucks", band=5, fmt="{:g}")


# ---------------------------------------------------------------------------
# loan sizing / term
# ---------------------------------------------------------------------------


@rule(
    key="loan_amount_range", label="Loan amount range", category="loan",
    description="Requested amount must fall within [min, max] for this program.",
    params=[Param("min", "float", "Minimum amount ($)", required=False),
            Param("max", "float", "Maximum amount ($)", required=False)],
)
def loan_amount_range(cfg, features):
    amount = _num(features.get("loan_amount"))
    lo = _num(cfg.get("min"))
    hi = _num(cfg.get("max"))
    label = "Loan amount"
    if amount is None:
        return _missing(cfg, label, "Loan amount")
    exp_parts = []
    if lo is not None:
        exp_parts.append(f"≥ ${lo:,.0f}")
    if hi is not None:
        exp_parts.append(f"≤ ${hi:,.0f}")
    exp = " and ".join(exp_parts) or "any"
    act = f"${amount:,.0f}"
    if lo is not None and amount < lo:
        return CriterionResult(
            "", label, EvalStatus.FAIL,
            f"Requested amount {act} is below this program's minimum of ${lo:,.0f}.",
            expected=exp, actual=act)
    if hi is not None and amount > hi:
        return CriterionResult(
            "", label, EvalStatus.FAIL,
            f"Requested amount {act} exceeds this program's maximum of ${hi:,.0f}.",
            expected=exp, actual=act)
    # margin: comfortably inside the band scores higher than right at the edge.
    margin = 1.0
    if lo is not None and hi is not None and hi > lo:
        center = (lo + hi) / 2
        half = (hi - lo) / 2
        margin = max(0.0, 1.0 - abs(amount - center) / half) if half else 1.0
    return CriterionResult(
        "", label, EvalStatus.PASS,
        f"Requested amount {act} is within the program range ({exp}).",
        expected=exp, actual=act, margin=margin)


@rule(
    key="max_loan_term", label="Maximum loan term", category="loan",
    description="Requested term (months) must not exceed the maximum.",
    params=[Param("max_months", "int", "Maximum term (months)")],
)
def max_loan_term(cfg, features):
    term = _num(features.get("loan_term_months"))
    hi = _num(cfg.get("max_months"))
    label = "Loan term"
    if hi is None:
        return CriterionResult("", label, EvalStatus.PASS, "No maximum configured.")
    if term is None:
        return _missing(cfg, label, "Loan term")
    exp, act = f"≤ {hi:.0f} months", f"{term:.0f} months"
    if term <= hi:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Requested term of {act} is within the {hi:.0f}-month maximum.",
                               expected=exp, actual=act, margin=1.0)
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Requested term of {act} exceeds the {hi:.0f}-month maximum.",
                           expected=exp, actual=act)


@rule(
    key="max_soft_costs_pct", label="Maximum soft costs %", category="loan",
    description="Soft costs must not exceed a percentage of the deal.",
    params=[Param("max_pct", "float", "Max soft costs (%)"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def max_soft_costs_pct(cfg, features):
    val = _num(features.get("soft_costs_pct"))
    hi = _num(cfg.get("max_pct"))
    label = "Soft costs"
    if hi is None:
        return CriterionResult("", label, EvalStatus.PASS, "No maximum configured.")
    if val is None:
        cfg = {**cfg, "on_missing": cfg.get("on_missing", "pass")}
        return _missing(cfg, label, "Soft costs %")
    exp, act = f"≤ {hi:g}%", f"{val:g}%"
    if val <= hi:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Soft costs of {act} are within the {hi:g}% maximum.",
                               expected=exp, actual=act)
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Soft costs of {act} exceed the {hi:g}% maximum.",
                           expected=exp, actual=act)


@rule(
    key="min_down_payment_pct", label="Minimum down payment %", category="loan",
    description="Down payment must be at least a percentage of the deal.",
    params=[Param("min_pct", "float", "Min down payment (%)"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_down_payment_pct(cfg, features):
    return _min_threshold(cfg, features, feature="down_payment_pct", key="min_pct",
                          label="Down payment", unit="%", band=10, fmt="{:g}")


# ---------------------------------------------------------------------------
# equipment
# ---------------------------------------------------------------------------


@rule(
    key="max_equipment_age", label="Maximum equipment age", category="equipment",
    description="Collateral must be no older than N years.",
    params=[Param("max_years", "int", "Max equipment age (years)"),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def max_equipment_age(cfg, features):
    age = _num(features.get("equipment_age_years"))
    hi = _num(cfg.get("max_years"))
    label = "Equipment age"
    if hi is None:
        return CriterionResult("", label, EvalStatus.PASS, "No maximum configured.")
    if age is None:
        return _missing(cfg, label, "Equipment age")
    exp, act = f"≤ {hi:g} yrs", f"{age:g} yrs"
    if age <= hi:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Equipment age of {act} is within the {hi:g}-year maximum.",
                               expected=exp, actual=act, margin=_margin(hi - age, 0, hi))
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Equipment age of {act} exceeds the {hi:g}-year maximum.",
                           expected=exp, actual=act)


@rule(
    key="excluded_equipment_types", label="Excluded equipment types", category="equipment",
    description="Reject if the equipment type is on the exclusion list.",
    params=[Param("types", "enum[]", "Excluded equipment types", options_enum="EquipmentType")],
)
def excluded_equipment_types(cfg, features):
    excluded = set(cfg.get("types", []))
    et = features.get("equipment_type")
    label = "Equipment eligibility"
    if et is None:
        return _missing({"on_missing": "warn"}, label, "Equipment type")
    if et in excluded:
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"Equipment type '{et}' is on this lender's excluded list.",
                               expected="not excluded", actual=str(et))
    return CriterionResult("", label, EvalStatus.PASS,
                           f"Equipment type '{et}' is eligible.",
                           expected="not excluded", actual=str(et))


# ---------------------------------------------------------------------------
# industry / geography
# ---------------------------------------------------------------------------


@rule(
    key="excluded_industries", label="Excluded industries", category="industry",
    default_severity=RuleSeverity.KNOCKOUT,
    description="Reject if the applicant's industry is on the exclusion list.",
    params=[Param("industries", "enum[]", "Excluded industries", options_enum="Industry")],
)
def excluded_industries(cfg, features):
    excluded = set(cfg.get("industries", []))
    ind = features.get("industry")
    label = "Industry eligibility"
    if ind is None:
        return _missing({"on_missing": "warn"}, label, "Industry")
    if ind in excluded:
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"Industry '{ind}' is on this lender's excluded list.",
                               expected="not excluded", actual=str(ind))
    return CriterionResult("", label, EvalStatus.PASS,
                           f"Industry '{ind}' is not excluded.",
                           expected="not excluded", actual=str(ind))


@rule(
    key="allowed_industries", label="Allowed industries (whitelist)", category="industry",
    description="Only the listed industries are eligible for this program.",
    params=[Param("industries", "enum[]", "Allowed industries", options_enum="Industry")],
)
def allowed_industries(cfg, features):
    allowed = set(cfg.get("industries", []))
    ind = features.get("industry")
    label = "Industry whitelist"
    if not allowed:
        return CriterionResult("", label, EvalStatus.PASS, "No whitelist configured.")
    if ind is None:
        return _missing({"on_missing": "warn"}, label, "Industry")
    if ind in allowed:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Industry '{ind}' is eligible for this program.",
                               expected="in allowed list", actual=str(ind))
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Industry '{ind}' is not in this program's eligible-industry list.",
                           expected="in allowed list", actual=str(ind))


@rule(
    key="excluded_states", label="Excluded states", category="geography",
    default_severity=RuleSeverity.KNOCKOUT,
    description="Reject if the business state is on the exclusion list.",
    params=[Param("states", "string[]", "Excluded 2-letter states")],
)
def excluded_states(cfg, features):
    excluded = {s.upper() for s in cfg.get("states", [])}
    st = features.get("state")
    label = "Geographic eligibility"
    if st is None:
        return _missing({"on_missing": "warn"}, label, "Business state")
    if str(st).upper() in excluded:
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"This lender does not lend in {st}.",
                               expected="not excluded", actual=str(st))
    return CriterionResult("", label, EvalStatus.PASS,
                           f"State {st} is eligible.",
                           expected="not excluded", actual=str(st))


@rule(
    key="non_trucking_only", label="Non-trucking only", category="industry",
    default_severity=RuleSeverity.KNOCKOUT,
    description="Program does not accept trucking/transportation industries.",
    params=[],
)
def non_trucking_only(cfg, features):
    label = "Non-trucking requirement"
    if features.get("is_trucking"):
        return CriterionResult("", label, EvalStatus.FAIL,
                               "This program does not finance trucking/transportation applicants.",
                               expected="non-trucking", actual="trucking")
    return CriterionResult("", label, EvalStatus.PASS,
                           "Applicant is non-trucking.",
                           expected="non-trucking", actual="non-trucking")


# ---------------------------------------------------------------------------
# derogatory credit knockouts (boolean flags)
# ---------------------------------------------------------------------------


def _flag_clear(
    features: FeatureSet,
    *,
    flag: str,
    label: str,
    bad_msg: str,
    good_msg: str,
) -> CriterionResult:
    """Generic 'this derog flag must be absent' check. Missing == assumed clean."""
    if features.get(flag):
        return CriterionResult("", label, EvalStatus.FAIL, bad_msg,
                               expected="none", actual="present")
    return CriterionResult("", label, EvalStatus.PASS, good_msg,
                           expected="none", actual="none")


@rule(
    key="no_open_judgments", label="No open judgments", category="credit",
    default_severity=RuleSeverity.KNOCKOUT, params=[],
)
def no_open_judgments(cfg, features):
    return _flag_clear(features, flag="has_open_judgments", label="Open judgments",
                       bad_msg="Open judgments in credit history are not accepted.",
                       good_msg="No open judgments reported.")


@rule(
    key="no_foreclosures", label="No foreclosures", category="credit",
    default_severity=RuleSeverity.KNOCKOUT, params=[],
)
def no_foreclosures(cfg, features):
    return _flag_clear(features, flag="has_foreclosures", label="Foreclosures",
                       bad_msg="Foreclosures in credit history are not accepted.",
                       good_msg="No foreclosures reported.")


@rule(
    key="no_repossessions", label="No repossessions", category="credit",
    default_severity=RuleSeverity.KNOCKOUT, params=[],
)
def no_repossessions(cfg, features):
    return _flag_clear(features, flag="has_repossessions", label="Repossessions",
                       bad_msg="Repossessions in credit history are not accepted.",
                       good_msg="No repossessions reported.")


@rule(
    key="no_tax_liens", label="No tax liens", category="credit",
    default_severity=RuleSeverity.KNOCKOUT, params=[],
)
def no_tax_liens(cfg, features):
    return _flag_clear(features, flag="has_tax_liens", label="Tax liens",
                       bad_msg="Tax liens are not accepted.",
                       good_msg="No tax liens reported.")


@rule(
    key="no_recent_collections", label="No recent collections/charge-offs", category="credit",
    default_severity=RuleSeverity.KNOCKOUT,
    description="No collections or charge-offs within the last N years.",
    params=[Param("years", "int", "Look-back window (years)")],
)
def no_recent_collections(cfg, features):
    label = "Recent collections / charge-offs"
    years = _num(cfg.get("years")) or 0
    last = _num(features.get("collections_years_ago"))
    has = features.get("has_recent_collections")
    if has is False and last is None:
        return CriterionResult("", label, EvalStatus.PASS,
                               "No recent collections or charge-offs reported.",
                               expected=f"none in {years:g} yrs", actual="none")
    if last is not None and last >= years:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Most recent collection/charge-off was {last:g} years ago "
                               f"(outside the {years:g}-year window).",
                               expected=f"none in {years:g} yrs", actual=f"{last:g} yrs ago")
    if has or (last is not None and last < years):
        ago = f"{last:g} yrs ago" if last is not None else "within window"
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"Collections/charge-offs within the last {years:g} years are not accepted.",
                               expected=f"none in {years:g} yrs", actual=ago)
    return CriterionResult("", label, EvalStatus.PASS,
                           "No recent collections or charge-offs reported.",
                           expected=f"none in {years:g} yrs", actual="none")


@rule(
    key="no_bankruptcy_within_years", label="Bankruptcy seasoning", category="credit",
    default_severity=RuleSeverity.KNOCKOUT,
    description="Any bankruptcy must be discharged at least N years ago "
                "(use a very large N to reject any bankruptcy outright).",
    params=[Param("years", "int", "Min years since discharge")],
)
def no_bankruptcy_within_years(cfg, features):
    label = "Bankruptcy seasoning"
    years = _num(cfg.get("years")) or 0
    has_bk = features.get("bankruptcy")
    since = _num(features.get("bankruptcy_years_since_discharge"))
    if not has_bk:
        return CriterionResult("", label, EvalStatus.PASS,
                               "No bankruptcy reported.",
                               expected=f"discharged ≥ {years:g} yrs ago", actual="none")
    if since is None:
        return _missing(cfg, label, "Years since bankruptcy discharge")
    exp = f"discharged ≥ {years:g} yrs ago"
    act = f"{since:g} yrs ago"
    if since >= years:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Bankruptcy was discharged {act}, satisfying the "
                               f"{years:g}-year seasoning requirement.",
                               expected=exp, actual=act)
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Bankruptcy discharged only {act}; this lender requires at least "
                           f"{years:g} years since discharge.",
                           expected=exp, actual=act)


# ---------------------------------------------------------------------------
# borrower attribute gates (booleans)
# ---------------------------------------------------------------------------


def _require_true(
    features: FeatureSet, *, feature: str, label: str, req_msg: str, ok_msg: str,
    on_missing: str = "fail",
) -> CriterionResult:
    val = features.get(feature)
    if val is None:
        return _missing({"on_missing": on_missing}, label, label)
    if val:
        return CriterionResult("", label, EvalStatus.PASS, ok_msg,
                               expected="required", actual="yes")
    return CriterionResult("", label, EvalStatus.FAIL, req_msg,
                           expected="required", actual="no")


@rule(
    key="requires_homeownership", label="Homeownership required", category="borrower",
    default_severity=RuleSeverity.QUALIFICATION, params=[],
)
def requires_homeownership(cfg, features):
    return _require_true(features, feature="homeownership", label="Homeownership",
                         req_msg="This program requires the guarantor to be a homeowner.",
                         ok_msg="Guarantor is a homeowner.")


@rule(
    key="requires_us_citizen", label="US citizen required", category="borrower",
    default_severity=RuleSeverity.KNOCKOUT, params=[],
)
def requires_us_citizen(cfg, features):
    return _require_true(features, feature="us_citizen", label="US citizenship",
                         req_msg="This lender only finances US citizens.",
                         ok_msg="Applicant is a US citizen.")


@rule(
    key="requires_cdl", label="CDL required", category="borrower",
    description="A commercial driver's license is required (for CDL equipment).",
    params=[Param("min_years", "float", "Min years holding CDL", required=False),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def requires_cdl(cfg, features):
    label = "CDL requirement"
    has = features.get("has_cdl")
    if has is None:
        return _missing({"on_missing": cfg.get("on_missing", "warn")}, label, "CDL status")
    if not has:
        return CriterionResult("", label, EvalStatus.FAIL,
                               "A commercial driver's license is required for this program.",
                               expected="CDL held", actual="no CDL")
    min_years = _num(cfg.get("min_years"))
    if min_years:
        yrs = _num(features.get("cdl_years"))
        if yrs is None:
            return _missing({"on_missing": "warn"}, label, "CDL years")
        if yrs < min_years:
            return CriterionResult("", label, EvalStatus.FAIL,
                                   f"CDL held for {yrs:g} years; {min_years:g} years required.",
                                   expected=f"≥ {min_years:g} yrs CDL", actual=f"{yrs:g} yrs")
    return CriterionResult("", label, EvalStatus.PASS, "CDL requirement satisfied.",
                           expected="CDL held", actual="yes")


@rule(
    key="requires_personal_guarantee", label="Personal guarantee required", category="borrower",
    default_severity=RuleSeverity.QUALIFICATION, params=[],
)
def requires_personal_guarantee(cfg, features):
    return _require_true(features, feature="has_personal_guarantee",
                         label="Personal guarantee",
                         req_msg="A personal guarantee is required for this program.",
                         ok_msg="Personal guarantee provided.")


# ---------------------------------------------------------------------------
# comparable credit / revolving debt
# ---------------------------------------------------------------------------


@rule(
    key="min_comparable_credit_pct", label="Comparable business credit", category="credit",
    description="Requires comparable prior borrowing of at least X% of the requested "
                "amount. Supports flat (min_pct) or amount-tiered (tiers) thresholds.",
    params=[Param("min_pct", "float", "Min comparable %", required=False),
            Param("tiers", "string", "Amount tiers JSON [{min,max,pct}]", required=False),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def min_comparable_credit_pct(cfg, features):
    label = "Comparable business credit"
    amount = _num(features.get("loan_amount"))
    actual_pct = _num(features.get("comparable_credit_pct"))
    # Resolve the required percentage, honouring amount tiers if present.
    required = _num(cfg.get("min_pct"))
    tiers = cfg.get("tiers") or []
    if tiers and amount is not None:
        required = None
        for t in tiers:
            lo = _num(t.get("min")) or 0
            hi = _num(t.get("max"))
            if amount >= lo and (hi is None or amount <= hi):
                required = _num(t.get("pct"))
                break
    if required is None:
        return CriterionResult("", label, EvalStatus.PASS,
                               "No comparable-credit requirement applies at this amount.")
    if actual_pct is None:
        return _missing({"on_missing": cfg.get("on_missing", "warn")}, label,
                        "Comparable business credit %")
    exp, act = f"≥ {required:g}% of request", f"{actual_pct:g}%"
    if actual_pct >= required:
        return CriterionResult("", label, EvalStatus.PASS,
                               f"Comparable borrowing of {act} meets the {required:g}% requirement.",
                               expected=exp, actual=act, margin=_margin(actual_pct, required, 50))
    return CriterionResult("", label, EvalStatus.FAIL,
                           f"Comparable borrowing of {act} is below the required {required:g}% "
                           f"of the requested amount.",
                           expected=exp, actual=act)


@rule(
    key="max_personal_revolving", label="Personal revolving debt limit", category="credit",
    description="Caps personal revolving debt (and optionally revolving + unsecured).",
    params=[Param("max_revolving", "float", "Max revolving ($)", required=False),
            Param("max_revolving_plus_unsecured", "float", "Max revolving + unsecured ($)",
                  required=False),
            Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def max_personal_revolving(cfg, features):
    label = "Personal revolving debt"
    rev = _num(features.get("personal_revolving_balance"))
    uns = _num(features.get("unsecured_debt")) or 0.0
    max_rev = _num(cfg.get("max_revolving"))
    max_combo = _num(cfg.get("max_revolving_plus_unsecured"))
    if rev is None:
        return _missing({"on_missing": cfg.get("on_missing", "warn")}, label,
                        "Personal revolving balance")
    if max_rev is not None and rev > max_rev:
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"Personal revolving debt of ${rev:,.0f} exceeds the ${max_rev:,.0f} limit.",
                               expected=f"≤ ${max_rev:,.0f}", actual=f"${rev:,.0f}")
    if max_combo is not None and (rev + uns) > max_combo:
        return CriterionResult("", label, EvalStatus.FAIL,
                               f"Revolving + unsecured debt of ${rev + uns:,.0f} exceeds the "
                               f"${max_combo:,.0f} limit.",
                               expected=f"≤ ${max_combo:,.0f} combined",
                               actual=f"${rev + uns:,.0f}")
    return CriterionResult("", label, EvalStatus.PASS,
                           "Personal revolving debt is within limits.",
                           expected="within limits", actual=f"${rev:,.0f}")


# ---------------------------------------------------------------------------
# program prerequisites (applicability gates) — produce NOT_APPLICABLE, not FAIL
# ---------------------------------------------------------------------------


def _prereq(ok: bool, label: str, applicable_msg: str, na_msg: str) -> CriterionResult:
    if ok:
        return CriterionResult("", label, EvalStatus.PASS, applicable_msg)
    return CriterionResult("", label, EvalStatus.NOT_APPLICABLE, na_msg,
                           severity=RuleSeverity.PREREQUISITE)


@rule(
    key="requires_paynet_present", label="Requires PayNet score", category="prerequisite",
    default_severity=RuleSeverity.PREREQUISITE,
    description="Program only applies when a PayNet score is available.", params=[],
)
def requires_paynet_present(cfg, features):
    return _prereq(features.has("paynet"), "PayNet availability",
                   "PayNet score available.",
                   "No PayNet score — this program does not apply.")


@rule(
    key="requires_no_paynet", label="Requires no PayNet score", category="prerequisite",
    default_severity=RuleSeverity.PREREQUISITE,
    description="Program (no-PayNet tier) only applies when PayNet is absent.", params=[],
)
def requires_no_paynet(cfg, features):
    return _prereq(not features.has("paynet"), "No-PayNet path",
                   "No PayNet score — no-PayNet tier applies.",
                   "PayNet score present — standard tier applies instead.")


@rule(
    key="requires_personal_guarantee_present", label="Requires a personal guarantor",
    category="prerequisite", default_severity=RuleSeverity.PREREQUISITE,
    description="Program only applies when a personal guarantor (FICO) exists.", params=[],
)
def requires_personal_guarantee_present(cfg, features):
    return _prereq(bool(features.get("has_personal_guarantee")), "Guarantor present",
                   "Personal guarantor present.",
                   "No personal guarantor — this program does not apply.")


@rule(
    key="requires_corp_only", label="Requires corp-only (no guarantor)",
    category="prerequisite", default_severity=RuleSeverity.PREREQUISITE,
    description="Program (corp-only tier) only applies with no personal guarantor.", params=[],
)
def requires_corp_only(cfg, features):
    return _prereq(bool(features.get("corp_only")), "Corp-only path",
                   "No personal guarantor — corp-only tier applies.",
                   "Personal guarantor present — corp-only tier does not apply.")


@rule(
    key="requires_trucking", label="Requires trucking applicant",
    category="prerequisite", default_severity=RuleSeverity.PREREQUISITE,
    description="Program (trucking tier) only applies to trucking applicants.", params=[],
)
def requires_trucking(cfg, features):
    return _prereq(bool(features.get("is_trucking")), "Trucking path",
                   "Trucking applicant — trucking tier applies.",
                   "Non-trucking applicant — trucking tier does not apply.")


@rule(
    key="requires_startup", label="Requires start-up business",
    category="prerequisite", default_severity=RuleSeverity.PREREQUISITE,
    description="Program (start-up tier) only applies to start-up businesses.", params=[],
)
def requires_startup(cfg, features):
    return _prereq(bool(features.get("is_startup")), "Start-up path",
                   "Start-up business — start-up tier applies.",
                   "Established business — start-up tier does not apply.")


@rule(
    key="requires_established", label="Requires established business",
    category="prerequisite", default_severity=RuleSeverity.PREREQUISITE,
    description="Program only applies to established (non-start-up) businesses.", params=[],
)
def requires_established(cfg, features):
    is_startup = features.get("is_startup")
    return _prereq(is_startup is False, "Established path",
                   "Established business — this tier applies.",
                   "Start-up business — this established-only tier does not apply.")


# ---------------------------------------------------------------------------
# preferences (soft signals — never block, only warn / nudge score)
# ---------------------------------------------------------------------------


@rule(
    key="prefers_secondary_income", label="Prefers secondary income", category="preference",
    default_severity=RuleSeverity.PREFERENCE,
    description="Soft preference for a secondary income source (working spouse, pension).",
    params=[],
)
def prefers_secondary_income(cfg, features):
    label = "Secondary income (preferred)"
    if features.get("has_secondary_income"):
        return CriterionResult("", label, EvalStatus.PASS,
                               "Secondary income source present.",
                               severity=RuleSeverity.PREFERENCE)
    return CriterionResult("", label, EvalStatus.WARNING,
                           "Lender prefers a secondary income source (e.g. working spouse/pension).",
                           severity=RuleSeverity.PREFERENCE)


@rule(
    key="no_private_party_sale", label="No private-party sale", category="equipment",
    description="Private-party (non-dealer) sales are not eligible for this program.",
    params=[Param("on_missing", "string", "If missing (fail/warn/pass)", required=False)],
)
def no_private_party_sale(cfg, features):
    label = "Private-party sale"
    if features.get("is_private_party_sale"):
        return CriterionResult("", label, EvalStatus.FAIL,
                               "Private-party sales are not eligible for this program.",
                               expected="dealer sale", actual="private party")
    return CriterionResult("", label, EvalStatus.PASS,
                           "Dealer/vendor sale (not private party).",
                           expected="dealer sale", actual="dealer")
