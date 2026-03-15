"""Experiment evaluator — scores research task outcomes.

Provides multi-metric evaluation of artifacts produced by operator
execution.  The evaluator is used by the :class:`RuntimeController` to
close the plan → execute → evaluate → replan loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    """Structured evaluation outcome.

    Attributes:
        task_id: Identifier of the task that was evaluated.
        metrics: Individual metric name → value pairs.
        score: Composite score in [0, 1].
        details: Human-readable explanation.
    """

    task_id: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "metrics": dict(self.metrics),
            "score": self.score,
            "details": self.details,
        }


class ExperimentEvaluator:
    """Evaluates artifacts produced for a research task.

    Scoring dimensions:
        * artifact_count — did the operator produce output?
        * completion — binary, at least one artifact present.
        * consistency — basic cross-artifact consistency check.
        * confidence — average ``confidence`` field when present.

    Custom metric functions can be added via :meth:`register_metric`.
    """

    def __init__(self) -> None:
        self._custom_metrics: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_metric(
        self,
        name: str,
        fn: Any,
    ) -> None:
        """Register a custom metric ``fn(task_dict, artifacts) -> float``."""
        self._custom_metrics[name] = fn

    def evaluate(
        self,
        task: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> EvaluationResult:
        """Evaluate *artifacts* produced for *task*.

        Args:
            task: Task dict (must contain ``task_id``).
            artifacts: List of artifact dicts.

        Returns:
            :class:`EvaluationResult` with computed metrics and composite score.
        """
        metrics: dict[str, float] = {}

        # Built-in metrics
        metrics["artifact_count"] = min(float(len(artifacts)), 5.0) / 5.0
        metrics["completion"] = 1.0 if artifacts else 0.0
        metrics["consistency"] = self._check_consistency(artifacts)
        metrics["confidence"] = self._avg_confidence(artifacts)

        # Custom metrics
        for name, fn in self._custom_metrics.items():
            try:
                metrics[name] = float(fn(task, artifacts))
            except Exception:
                metrics[name] = 0.0

        score = sum(metrics.values()) / max(len(metrics), 1)

        return EvaluationResult(
            task_id=task.get("task_id", ""),
            metrics=metrics,
            score=score,
            details=f"Evaluated {len(artifacts)} artifact(s) across {len(metrics)} metrics",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_consistency(artifacts: list[dict[str, Any]]) -> float:
        """Simple consistency heuristic.

        Returns 1.0 when all artifacts share the same ``artifact_type``,
        otherwise penalises proportionally.
        """
        if not artifacts:
            return 0.0
        types = {a.get("artifact_type", "") for a in artifacts}
        return 1.0 / len(types)

    @staticmethod
    def _avg_confidence(artifacts: list[dict[str, Any]]) -> float:
        """Average confidence across artifacts (defaults to 0.5 when absent)."""
        if not artifacts:
            return 0.0
        values = [a.get("confidence", 0.5) for a in artifacts]
        return sum(values) / len(values)
