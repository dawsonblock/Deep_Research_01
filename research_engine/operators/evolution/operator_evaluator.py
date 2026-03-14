"""Operator evaluator — computes scores from metrics and downstream outcomes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.operators.evolution.operator_metrics import OperatorMetricsStore


@dataclass
class EvaluationResult:
    """Result of evaluating an operator version."""
    operator_family: str
    version: str
    composite_score: float = 0.0
    metric_scores: dict[str, float] = field(default_factory=dict)
    run_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_family": self.operator_family,
            "version": self.version,
            "composite_score": self.composite_score,
            "metric_scores": self.metric_scores,
            "run_count": self.run_count,
            "details": self.details,
        }


class OperatorEvaluator:
    """Computes quality scores for operator versions from metrics."""

    # Weights for composite scoring
    DEFAULT_WEIGHTS: dict[str, float] = {
        "success_rate": 0.35,
        "avg_confidence": 0.25,
        "runtime_efficiency": 0.15,
        "stability": 0.25,
    }

    def __init__(
        self,
        metrics_store: OperatorMetricsStore,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.metrics_store = metrics_store
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

    def evaluate_operator(
        self,
        operator_family: str,
        version: str,
    ) -> EvaluationResult:
        """Evaluate a specific operator version based on recorded metrics."""
        key = f"{operator_family}:{version}"
        metrics = self.metrics_store.get_metrics(key)

        if metrics is None or metrics.total_runs == 0:
            return EvaluationResult(
                operator_family=operator_family,
                version=version,
                composite_score=0.0,
                run_count=0,
            )

        metric_scores: dict[str, float] = {}

        # Success rate (already 0-1)
        metric_scores["success_rate"] = metrics.success_rate

        # Average confidence (already 0-1)
        metric_scores["avg_confidence"] = metrics.avg_confidence

        # Runtime efficiency (inverse, normalized: faster = higher score)
        metric_scores["runtime_efficiency"] = 1.0 / (1.0 + metrics.avg_runtime)

        # Stability (fewer failure modes = higher stability)
        failure_mode_count = len(metrics.failure_modes)
        metric_scores["stability"] = 1.0 / (1.0 + failure_mode_count)

        # Compute composite score
        composite = sum(
            metric_scores.get(k, 0.0) * w
            for k, w in self.weights.items()
        )

        return EvaluationResult(
            operator_family=operator_family,
            version=version,
            composite_score=round(composite, 4),
            metric_scores=metric_scores,
            run_count=metrics.total_runs,
            details={"failure_modes": metrics.failure_modes},
        )

    def compare_versions(
        self,
        operator_family: str,
        versions: list[str],
    ) -> list[EvaluationResult]:
        """Evaluate and rank multiple versions of an operator family."""
        results = [
            self.evaluate_operator(operator_family, v)
            for v in versions
        ]
        return sorted(results, key=lambda r: r.composite_score, reverse=True)
