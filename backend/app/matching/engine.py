"""The matching engine.

Given a normalized application (FeatureSet) and a lender's policy, decide:
  * eligibility (yes/no),
  * the best matching program/tier (if eligible),
  * specific rejection reasons (if ineligible),
  * a fit score (0-100) for ranking.

The engine is intentionally **ORM-free**: it consumes the lightweight
``LenderPolicy`` / ``ProgramPolicy`` dataclasses below. ``build_lender_policy``
adapts a persisted ORM ``Lender`` into them. This keeps the decision logic a pure
function of (policy, features) — the thing we most want to unit-test.

Decision procedure per lender:
  1. Evaluate lender-wide **knockout** rules. Any FAIL => ineligible.
  2. For each **program**: evaluate its **prerequisite** rules (applicability
     gate). If not applicable, the program is skipped (NOT_APPLICABLE). Otherwise
     evaluate its **qualification** rules; the program *qualifies* iff none of
     them block.
  3. The lender is **eligible** iff no knockout fired AND at least one program
     qualifies. The **best program** is the qualifying one with the lowest rank.
  4. Compute the fit score from the best program (eligible) or the closest
     program + knockouts (ineligible).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.matching.scoring import score_eligible, score_ineligible
from app.models.enums import EvalStatus, RuleSeverity
from app.rules import registry
from app.rules.types import CriterionResult, FeatureSet, RuleSpec


# --------------------------------------------------------------------------- #
# Engine input (ORM-free)
# --------------------------------------------------------------------------- #
@dataclass
class ProgramPolicy:
    id: int | None
    name: str
    rank: int = 1
    rate: float | None = None
    credit_grade: str | None = None
    prerequisite_rules: list[RuleSpec] = field(default_factory=list)
    qualification_rules: list[RuleSpec] = field(default_factory=list)


@dataclass
class LenderPolicy:
    id: int | None
    name: str
    knockout_rules: list[RuleSpec] = field(default_factory=list)
    programs: list[ProgramPolicy] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Engine output (ORM-free)
# --------------------------------------------------------------------------- #
@dataclass
class ProgramEvaluation:
    program_id: int | None
    program_name: str
    rank: int
    rate: float | None
    credit_grade: str | None
    applicable: bool
    qualified: bool
    prerequisite_results: list[CriterionResult]
    qualification_results: list[CriterionResult]

    @property
    def blocking_results(self) -> list[CriterionResult]:
        return [r for r in self.qualification_results if r.blocks_eligibility]


@dataclass
class LenderEvaluation:
    lender_id: int | None
    lender_name: str
    eligible: bool
    fit_score: float
    knockout_results: list[CriterionResult]
    program_evaluations: list[ProgramEvaluation]
    best_program: ProgramEvaluation | None
    reasons: list[str]


def _evaluate_rules(rules: list[RuleSpec], features: FeatureSet) -> list[CriterionResult]:
    out: list[CriterionResult] = []
    for spec in rules:
        result = registry.evaluate(spec.rule_type, spec.config, features)
        result.severity = spec.severity
        result.rule_id = spec.rule_id
        out.append(result)
    return out


def evaluate_lender(policy: LenderPolicy, features: FeatureSet) -> LenderEvaluation:
    # 1. Lender-wide knockouts.
    knockout_results = _evaluate_rules(policy.knockout_rules, features)
    knockout_failed = [r for r in knockout_results if r.blocks_eligibility]

    # 2. Programs.
    program_evals: list[ProgramEvaluation] = []
    for prog in policy.programs:
        prereq_results = _evaluate_rules(prog.prerequisite_rules, features)
        applicable = all(
            r.status != EvalStatus.NOT_APPLICABLE for r in prereq_results
        )
        qual_results = _evaluate_rules(prog.qualification_rules, features)
        blocks = [r for r in qual_results if r.blocks_eligibility]
        qualified = applicable and not blocks and not knockout_failed
        program_evals.append(
            ProgramEvaluation(
                program_id=prog.id,
                program_name=prog.name,
                rank=prog.rank,
                rate=prog.rate,
                credit_grade=prog.credit_grade,
                applicable=applicable,
                qualified=qualified,
                prerequisite_results=prereq_results,
                qualification_results=qual_results,
            )
        )

    # 3. Eligibility + best program.
    qualifying = [p for p in program_evals if p.qualified]
    eligible = bool(qualifying) and not knockout_failed
    best_program = min(qualifying, key=lambda p: p.rank) if qualifying else None

    # 4. Score + reasons.
    if eligible and best_program is not None:
        warning_count = sum(
            1 for r in best_program.qualification_results if r.status == EvalStatus.WARNING
        )
        fit_score = score_eligible(
            best_program.qualification_results, best_program.rank, warning_count
        )
        reasons = _eligible_reasons(best_program)
    else:
        closest = _closest_program(program_evals)
        gating = list(knockout_results)
        if closest is not None:
            gating += closest.qualification_results
        fit_score = score_ineligible(gating)
        reasons = _rejection_reasons(knockout_failed, closest)

    return LenderEvaluation(
        lender_id=policy.id,
        lender_name=policy.name,
        eligible=eligible,
        fit_score=fit_score,
        knockout_results=knockout_results,
        program_evaluations=program_evals,
        best_program=best_program,
        reasons=reasons,
    )


def _closest_program(program_evals: list[ProgramEvaluation]) -> ProgramEvaluation | None:
    """The applicable program with the fewest blocking criteria (best tier breaks
    ties) — i.e. the one the applicant came closest to qualifying for."""
    applicable = [p for p in program_evals if p.applicable]
    pool = applicable or program_evals
    if not pool:
        return None
    return min(pool, key=lambda p: (len(p.blocking_results), p.rank))


def _eligible_reasons(best: ProgramEvaluation) -> list[str]:
    reasons = [f"Qualifies for {best.program_name}."]
    warnings = [r.message for r in best.qualification_results if r.status == EvalStatus.WARNING]
    reasons.extend(warnings)
    return reasons


def _rejection_reasons(
    knockout_failed: list[CriterionResult],
    closest: ProgramEvaluation | None,
) -> list[str]:
    reasons = [r.message for r in knockout_failed]
    if not reasons and closest is not None:
        if not closest.applicable:
            reasons.extend(
                r.message
                for r in closest.prerequisite_results
                if r.status == EvalStatus.NOT_APPLICABLE
            )
        reasons.extend(r.message for r in closest.blocking_results)
    if not reasons:
        reasons.append("Application does not meet this lender's credit policy.")
    return reasons
