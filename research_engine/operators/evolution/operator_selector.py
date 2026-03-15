"""Operator selector — chooses best operator version and handles promotion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_engine.operators.evolution.operator_registry import VersionedOperatorRegistry
from research_engine.operators.evolution.operator_evaluator import OperatorEvaluator


@dataclass
class SelectionResult:
    """Result of a version selection decision."""
    operator_family: str
    selected_version: str
    score: float
    promoted: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_family": self.operator_family,
            "selected_version": self.selected_version,
            "score": self.score,
            "promoted": self.promoted,
            "reason": self.reason,
        }


class OperatorSelector:
    """Chooses the active operator version based on evaluation scores."""

    def __init__(
        self,
        registry: VersionedOperatorRegistry,
        evaluator: OperatorEvaluator,
        *,
        promotion_threshold: float = 0.1,
        min_runs: int = 5,
    ) -> None:
        self.registry = registry
        self.evaluator = evaluator
        self.promotion_threshold = promotion_threshold
        self.min_runs = min_runs

    def select_best(self, operator_family: str) -> SelectionResult:
        """Select the best version based on evaluation scores."""
        versions = self.registry.list_versions(operator_family)
        if not versions:
            return SelectionResult(
                operator_family=operator_family,
                selected_version="",
                score=0.0,
                reason="no versions registered",
            )

        version_strs = [v.version for v in versions]
        evaluations = self.evaluator.compare_versions(operator_family, version_strs)

        best = evaluations[0] if evaluations else None
        if best is None or best.run_count == 0:
            # Fall back to active version
            active = self.registry.active_version(operator_family)
            return SelectionResult(
                operator_family=operator_family,
                selected_version=active or version_strs[0],
                score=0.0,
                reason="no evaluation data, using active/first version",
            )

        return SelectionResult(
            operator_family=operator_family,
            selected_version=best.version,
            score=best.composite_score,
            reason=f"highest composite score: {best.composite_score:.4f}",
        )

    def promote_if_threshold(
        self,
        operator_family: str,
        candidate_version: str,
    ) -> SelectionResult:
        """Promote candidate if it exceeds active version by threshold margin."""
        active_ver = self.registry.active_version(operator_family)
        if active_ver is None:
            # No active version, promote candidate
            self.registry.set_active(operator_family, candidate_version)
            return SelectionResult(
                operator_family=operator_family,
                selected_version=candidate_version,
                score=0.0,
                promoted=True,
                reason="no active version, promoted candidate",
            )

        if active_ver == candidate_version:
            # Candidate is already the active version
            active_eval = self.evaluator.evaluate_operator(operator_family, active_ver)
            return SelectionResult(
                operator_family=operator_family,
                selected_version=active_ver,
                score=active_eval.composite_score,
                promoted=True,
                reason="candidate is already the active version",
            )

        # Evaluate both
        active_eval = self.evaluator.evaluate_operator(operator_family, active_ver)
        candidate_eval = self.evaluator.evaluate_operator(operator_family, candidate_version)

        # Require minimum runs
        if candidate_eval.run_count < self.min_runs:
            return SelectionResult(
                operator_family=operator_family,
                selected_version=active_ver,
                score=active_eval.composite_score,
                promoted=False,
                reason=f"candidate has only {candidate_eval.run_count} runs (min: {self.min_runs})",
            )

        improvement = candidate_eval.composite_score - active_eval.composite_score
        if improvement >= self.promotion_threshold:
            self.registry.set_active(operator_family, candidate_version)
            return SelectionResult(
                operator_family=operator_family,
                selected_version=candidate_version,
                score=candidate_eval.composite_score,
                promoted=True,
                reason=f"promoted: improvement {improvement:.4f} >= threshold {self.promotion_threshold}",
            )

        return SelectionResult(
            operator_family=operator_family,
            selected_version=active_ver,
            score=active_eval.composite_score,
            promoted=False,
            reason=f"not promoted: improvement {improvement:.4f} < threshold {self.promotion_threshold}",
        )
