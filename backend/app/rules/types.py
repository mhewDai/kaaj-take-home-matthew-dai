"""Pure-Python value types for the rule engine.

Nothing in ``app.rules`` imports SQLAlchemy or FastAPI — the engine operates on
plain dataclasses/dicts. That keeps the matching logic (the most important thing
to get right) trivially unit-testable and decoupled from persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import EvalStatus, RuleSeverity


@dataclass
class FeatureSet:
    """The normalized, derived view of a loan application the engine reasons over.

    Raw application input (start date, equipment year, ...) is transformed into
    these features by ``app.matching.features`` before evaluation. Evaluators only
    ever read features by name via :meth:`get`, never the ORM objects.
    """

    values: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        return self.values.get(name, default)

    def has(self, name: str) -> bool:
        return self.values.get(name) is not None

    def __getitem__(self, name: str) -> Any:
        return self.values[name]


@dataclass
class CriterionResult:
    """Structured outcome of evaluating one rule against one application.

    This is what powers the "which criteria met / didn't meet and why" UI. Every
    field is human-presentable; ``margin`` is the only machine-only field and is
    used by the fit-score calculation.
    """

    rule_type: str
    label: str
    status: EvalStatus
    message: str
    severity: RuleSeverity = RuleSeverity.QUALIFICATION
    expected: str | None = None
    actual: str | None = None
    # 0..1 — how comfortably a *passing* numeric rule cleared its threshold.
    # None when not meaningful (booleans, failures, list membership, ...).
    margin: float | None = None
    rule_id: int | None = None

    @property
    def passed(self) -> bool:
        return self.status == EvalStatus.PASS

    @property
    def blocks_eligibility(self) -> bool:
        """Whether this result should prevent approval.

        Preferences never block. Everything else blocks unless it cleanly passed
        or was not applicable.
        """
        if self.severity == RuleSeverity.PREFERENCE:
            return False
        return self.status in (
            EvalStatus.FAIL,
            EvalStatus.INSUFFICIENT_DATA,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "label": self.label,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity.value,
            "expected": self.expected,
            "actual": self.actual,
            "margin": self.margin,
            "rule_id": self.rule_id,
        }


@dataclass
class RuleSpec:
    """A rule as the engine consumes it — decoupled from the ORM row.

    ``rule_type`` selects the evaluator from the registry; ``config`` is the
    per-rule JSON (thresholds, lists, ...). ``severity`` decides how the result
    participates in the decision.
    """

    rule_type: str
    config: dict[str, Any]
    severity: RuleSeverity
    rule_id: int | None = None
