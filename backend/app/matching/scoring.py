"""Fit-score computation (0-100) used to rank lenders.

Design goals (see DECISIONS.md):
  * An **eligible** lender always outranks an **ineligible** one — eligibility is
    the dominant signal. Eligible scores live in [60, 100]; ineligible in [0, 55].
  * Among eligible lenders, prefer (a) more buffer above thresholds — a safer
    approval, (b) a better program tier — better pricing for the borrower, and
    (c) a cleaner profile (fewer warnings).
  * Among ineligible lenders, a near-miss (most criteria passed) ranks above a
    hopeless one, so the UI can surface "closest to qualifying".

Every input is already-computed CriterionResults, so scoring stays a pure
function and is easy to unit-test.
"""
from __future__ import annotations

from app.models.enums import EvalStatus, RuleSeverity
from app.rules.types import CriterionResult

# Eligible band: [BASE, 100]; ineligible band: [0, INELIGIBLE_MAX].
ELIGIBLE_BASE = 60.0
ELIGIBLE_SPAN = 40.0
INELIGIBLE_MAX = 55.0

W_MARGIN = 0.625   # 25 of the 40-pt span
W_TIER = 0.25      # 10 of the 40-pt span
W_CLEAN = 0.125    # 5 of the 40-pt span


def _tier_quality(rank: int) -> float:
    """1.0 for the best tier (rank 1), gently decaying for lower tiers."""
    return max(0.4, 1.0 - 0.12 * (max(1, rank) - 1))


def score_eligible(
    qualification_results: list[CriterionResult],
    program_rank: int,
    warning_count: int,
) -> float:
    margins = [
        r.margin
        for r in qualification_results
        if r.status == EvalStatus.PASS and r.margin is not None
    ]
    margin_score = (sum(margins) / len(margins)) if margins else 0.6
    tier_score = _tier_quality(program_rank)
    clean_score = 1.0 if warning_count == 0 else max(0.0, 1.0 - 0.25 * warning_count)

    composite = W_MARGIN * margin_score + W_TIER * tier_score + W_CLEAN * clean_score
    return round(ELIGIBLE_BASE + ELIGIBLE_SPAN * min(1.0, composite), 1)


def score_ineligible(gating_results: list[CriterionResult]) -> float:
    """Fraction of gating (non-preference) criteria that passed, scaled to band."""
    gating = [r for r in gating_results if r.severity != RuleSeverity.PREFERENCE]
    if not gating:
        return 0.0
    passed = sum(1 for r in gating if r.status == EvalStatus.PASS)
    return round(INELIGIBLE_MAX * (passed / len(gating)), 1)
