"""Rule engine package.

Importing this package registers every built-in evaluator (the import of
``evaluators`` has the side effect of running all the ``@rule`` decorators).
"""
from app.rules import evaluators  # noqa: F401  (side-effect: registers rules)
from app.rules.registry import Param, RuleType, registry, rule
from app.rules.types import CriterionResult, FeatureSet, RuleSpec

__all__ = [
    "registry",
    "rule",
    "Param",
    "RuleType",
    "CriterionResult",
    "FeatureSet",
    "RuleSpec",
]
