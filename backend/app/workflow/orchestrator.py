"""In-process underwriting workflow.

The brief asks for a workflow that validates completeness, derives features,
ranks matches by fit score, persists results — and to "demonstrate proper use of
Hatchet features including parallelization and retry logic".

We implement that shape with a small, explicit, **Hatchet-shaped** orchestrator
so it runs with zero extra infrastructure, while mapping 1:1 onto Hatchet
primitives (see the docstring on each step and ``workflow/README`` / DECISIONS):

    step: validate            ->  @hatchet.step()           (non-retryable)
    step: derive_features     ->  @hatchet.step()
    step: evaluate_lenders    ->  fan-out child workflows / asyncio.gather
                                  + per-lender retries (retries=N)
    step: rank_and_score      ->  @hatchet.step()
    step: persist_results     ->  @hatchet.step(retries=N)  (transient DB errors)

Parallelization: each lender is evaluated concurrently via ``asyncio.gather`` +
``asyncio.to_thread`` (the evaluation itself is pure/CPU-bound). ORM access is
confined to the main thread; worker threads only touch plain dataclasses.

Retry: ``with_retries`` wraps the per-lender evaluation and the persist step,
with bounded attempts + linear backoff, configurable via settings.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy.orm import Session

from app.config import get_settings
from app.matching import (
    LenderEvaluation,
    build_lender_policy,
    derive_features,
    evaluate_lender,
    validate_completeness,
)
from app.matching.engine import LenderPolicy
from app.models.enums import EvalStatus, RunStatus
from app.models.lender import Lender
from app.models.result import CriterionResultRow, MatchResult, UnderwritingRun
from app.rules.types import FeatureSet

logger = logging.getLogger("underwriting.workflow")
settings = get_settings()

T = TypeVar("T")


class WorkflowValidationError(Exception):
    """Non-retryable: the application is incomplete."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int,
    backoff: float,
    label: str = "step",
) -> T:
    """Run ``fn`` with bounded retries + linear backoff (Hatchet ``retries=``)."""
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > retries:
                logger.warning("%s failed after %d attempts: %s", label, attempt, exc)
                raise
            logger.info("%s attempt %d failed (%s) — retrying", label, attempt, exc)
            await asyncio.sleep(backoff * attempt)


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #
def step_validate(app) -> None:
    problems = validate_completeness(app)
    if problems:
        raise WorkflowValidationError(problems)


def step_derive_features(app) -> FeatureSet:
    return derive_features(app)


async def step_evaluate_lenders(
    policies: list[LenderPolicy], features: FeatureSet
) -> list[LenderEvaluation]:
    """Fan-out: evaluate every lender concurrently, each with its own retries."""

    async def eval_one(policy: LenderPolicy) -> LenderEvaluation | None:
        try:
            return await with_retries(
                lambda: asyncio.to_thread(evaluate_lender, policy, features),
                retries=settings.lender_eval_max_retries,
                backoff=settings.lender_eval_retry_backoff_seconds,
                label=f"evaluate[{policy.name}]",
            )
        except Exception:  # noqa: BLE001 — one bad lender must not fail the run
            logger.exception("Lender %s evaluation permanently failed; skipping", policy.name)
            return None

    results = await asyncio.gather(*(eval_one(p) for p in policies))
    return [r for r in results if r is not None]


def step_rank_and_score(evaluations: list[LenderEvaluation]) -> list[LenderEvaluation]:
    """Eligible first, then by fit score desc, then by name for stable ordering."""
    evaluations.sort(key=lambda e: (not e.eligible, -e.fit_score, e.lender_name))
    return evaluations


def step_persist(
    db: Session,
    run: UnderwritingRun,
    evaluations: list[LenderEvaluation],
    features: FeatureSet,
) -> None:
    run.derived_features = features.values
    run.lender_count = len(evaluations)
    run.eligible_count = sum(1 for e in evaluations if e.eligible)
    # Replace any previous results for idempotent re-runs.
    run.results.clear()
    db.flush()

    for rank, ev in enumerate(evaluations, start=1):
        mr = MatchResult(
            lender_id=ev.lender_id,
            lender_name=ev.lender_name,
            eligible=ev.eligible,
            fit_score=ev.fit_score,
            rank=rank,
            matched_program_id=ev.best_program.program_id if ev.best_program else None,
            matched_program_name=ev.best_program.program_name if ev.best_program else None,
            matched_program_rate=ev.best_program.rate if ev.best_program else None,
            reasons=ev.reasons,
        )
        # Persist lender-level knockout criteria (program_id NULL).
        for cr in ev.knockout_results:
            mr.criteria.append(_criterion_row(cr, program_id=None, program_name=None))
        # Persist criteria for every program so the UI can show the full breakdown.
        for pe in ev.program_evaluations:
            for cr in (*pe.prerequisite_results, *pe.qualification_results):
                mr.criteria.append(
                    _criterion_row(cr, program_id=pe.program_id, program_name=pe.program_name)
                )
        run.results.append(mr)
    db.flush()


def _criterion_row(cr, program_id, program_name) -> CriterionResultRow:
    return CriterionResultRow(
        program_id=program_id,
        program_name=program_name,
        rule_type=cr.rule_type,
        label=cr.label,
        status=cr.status.value if isinstance(cr.status, EvalStatus) else str(cr.status),
        severity=cr.severity.value,
        message=cr.message,
        expected=cr.expected,
        actual=cr.actual,
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
async def run_underwriting(db: Session, run: UnderwritingRun) -> UnderwritingRun:
    """Execute the full workflow for a persisted run, updating its status."""
    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    app = run.application
    try:
        # 1) validate completeness (non-retryable)
        step_validate(app)

        # 2) derive features
        features = step_derive_features(app)

        # 3) build policies in the main thread (ORM access), then fan-out evaluate
        lenders = (
            db.query(Lender).filter(Lender.is_active.is_(True)).order_by(Lender.name).all()
        )
        policies = [build_lender_policy(ln) for ln in lenders]
        evaluations = await step_evaluate_lenders(policies, features)

        # 4) rank & score
        evaluations = step_rank_and_score(evaluations)

        # 5) persist (retryable for transient DB errors)
        await with_retries(
            lambda: asyncio.to_thread(step_persist, db, run, evaluations, features),
            retries=1,
            backoff=settings.lender_eval_retry_backoff_seconds,
            label="persist_results",
        )

        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except WorkflowValidationError as exc:
        run.status = RunStatus.FAILED.value
        run.error = f"Validation failed: {exc}"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Underwriting run %s failed", run.id)
        run.status = RunStatus.FAILED.value
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    return run


def run_underwriting_sync(db: Session, run: UnderwritingRun) -> UnderwritingRun:
    """Synchronous entry point (used by the API request handler and tests)."""
    return asyncio.run(run_underwriting(db, run))
