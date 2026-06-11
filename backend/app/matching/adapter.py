"""Adapt persisted ORM lenders into the engine's ORM-free policy dataclasses."""
from __future__ import annotations

from app.matching.engine import LenderPolicy, ProgramPolicy
from app.models.enums import RuleSeverity
from app.models.lender import Lender, PolicyRule
from app.rules.types import RuleSpec


def _to_spec(rule: PolicyRule) -> RuleSpec:
    return RuleSpec(
        rule_type=rule.rule_type,
        config=rule.config or {},
        severity=RuleSeverity(rule.severity),
        rule_id=rule.id,
    )


def build_lender_policy(lender: Lender) -> LenderPolicy:
    knockouts = [
        _to_spec(r)
        for r in lender.rules
        if r.is_active and r.program_id is None
    ]
    programs: list[ProgramPolicy] = []
    for prog in lender.programs:
        if not prog.is_active:
            continue
        prereqs: list[RuleSpec] = []
        quals: list[RuleSpec] = []
        for r in prog.rules:
            if not r.is_active:
                continue
            spec = _to_spec(r)
            if spec.severity == RuleSeverity.PREREQUISITE:
                prereqs.append(spec)
            else:
                quals.append(spec)
        programs.append(
            ProgramPolicy(
                id=prog.id,
                name=prog.name,
                rank=prog.rank,
                rate=prog.rate,
                credit_grade=prog.credit_grade,
                prerequisite_rules=prereqs,
                qualification_rules=quals,
            )
        )
    return LenderPolicy(
        id=lender.id,
        name=lender.name,
        knockout_rules=knockouts,
        programs=programs,
    )
