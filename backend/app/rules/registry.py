"""The rule-type registry — the extension point of the whole platform.

Adding a brand-new *kind* of policy check is a single, local change:

    @rule(
        key="max_loan_term",
        label="Maximum loan term",
        category="loan",
        params=[Param("max_months", "int", "Max term (months)")],
    )
    def max_loan_term(cfg, features):
        ...
        return CriterionResult(...)

That registration simultaneously:
  * makes the check evaluable by the engine (keyed by ``key``),
  * tells the frontend policy editor what parameters the rule takes (``params``),
    so the UI can render an edit form for it with zero bespoke code,
  * documents the rule (``label`` / ``description`` / ``category``).

Editing an *existing* policy (changing a threshold, adding a state to an
exclusion list) never touches code — it is a data edit on a PolicyRule row.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import EvalStatus, RuleSeverity
from app.rules.types import CriterionResult, FeatureSet

EvaluatorFn = Callable[[dict[str, Any], FeatureSet], CriterionResult]


@dataclass(frozen=True)
class Param:
    """Describes one config parameter of a rule type (drives the editor UI)."""

    name: str
    type: str  # "int" | "float" | "string" | "bool" | "string[]" | "enum[]"
    label: str
    required: bool = True
    options_enum: str | None = None  # name of an enum to populate choices from
    help: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "label": self.label,
            "required": self.required,
            "options_enum": self.options_enum,
            "help": self.help,
        }


@dataclass
class RuleType:
    key: str
    label: str
    evaluator: EvaluatorFn
    category: str = "general"
    description: str = ""
    default_severity: RuleSeverity = RuleSeverity.QUALIFICATION
    params: list[Param] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "default_severity": self.default_severity.value,
            "params": [p.to_dict() for p in self.params],
        }


class RuleRegistry:
    def __init__(self) -> None:
        self._types: dict[str, RuleType] = {}

    def register(self, rule_type: RuleType) -> None:
        if rule_type.key in self._types:
            raise ValueError(f"Duplicate rule type: {rule_type.key}")
        self._types[rule_type.key] = rule_type

    def get(self, key: str) -> RuleType:
        if key not in self._types:
            raise KeyError(f"Unknown rule type: {key!r}")
        return self._types[key]

    def has(self, key: str) -> bool:
        return key in self._types

    def all(self) -> list[RuleType]:
        return sorted(self._types.values(), key=lambda r: (r.category, r.key))

    def evaluate(
        self,
        rule_type: str,
        config: dict[str, Any],
        features: FeatureSet,
    ) -> CriterionResult:
        """Run one rule. Unknown rule types and evaluator crashes degrade
        gracefully into an INSUFFICIENT_DATA result rather than blowing up an
        entire underwriting run."""
        if not self.has(rule_type):
            return CriterionResult(
                rule_type=rule_type,
                label=rule_type,
                status=EvalStatus.INSUFFICIENT_DATA,
                message=f"Unknown rule type '{rule_type}' — skipped.",
            )
        rt = self.get(rule_type)
        try:
            result = rt.evaluator(config or {}, features)
        except Exception as exc:  # pragma: no cover - defensive
            return CriterionResult(
                rule_type=rule_type,
                label=rt.label,
                status=EvalStatus.INSUFFICIENT_DATA,
                message=f"Could not evaluate '{rt.label}': {exc}",
            )
        result.rule_type = rule_type
        if not result.label:
            result.label = rt.label
        return result


# Global singleton registry plus the decorator used to populate it.
registry = RuleRegistry()


def rule(
    key: str,
    label: str,
    *,
    category: str = "general",
    description: str = "",
    default_severity: RuleSeverity = RuleSeverity.QUALIFICATION,
    params: list[Param] | None = None,
) -> Callable[[EvaluatorFn], EvaluatorFn]:
    def decorator(fn: EvaluatorFn) -> EvaluatorFn:
        registry.register(
            RuleType(
                key=key,
                label=label,
                evaluator=fn,
                category=category,
                description=description or (fn.__doc__ or "").strip(),
                default_severity=default_severity,
                params=params or [],
            )
        )
        return fn

    return decorator
