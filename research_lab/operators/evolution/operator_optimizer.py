"""Operator optimization strategies based on performance metrics."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

from research_lab.operators.evolution.operator_metrics import OperatorMetrics


class OptimizationStrategy(Enum):
    PROMPT_IMPROVEMENT = "prompt_improvement"
    PARAMETER_TUNING = "parameter_tuning"
    ALGORITHM_REPLACEMENT = "algorithm_replacement"


@dataclass
class OptimizationRecommendation:
    """A recommendation for how to improve an operator."""
    operator_name: str
    strategy: OptimizationStrategy
    reason: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "operator_name": self.operator_name,
            "strategy": self.strategy.value,
            "reason": self.reason,
            "details": self.details,
        }


class OperatorOptimizer:
    """Analyzes operator metrics and recommends improvements."""

    def __init__(
        self,
        low_success_threshold: float = 0.6,
        low_confidence_threshold: float = 0.5,
        high_runtime_threshold: float = 10.0,
    ) -> None:
        self.low_success_threshold = low_success_threshold
        self.low_confidence_threshold = low_confidence_threshold
        self.high_runtime_threshold = high_runtime_threshold

    def analyze(self, metrics: OperatorMetrics) -> list[OptimizationRecommendation]:
        """Produce optimization recommendations for an operator."""
        recommendations: list[OptimizationRecommendation] = []

        if metrics.total_runs == 0:
            return recommendations

        # Low success rate -> algorithm replacement
        if metrics.success_rate < self.low_success_threshold:
            recommendations.append(
                OptimizationRecommendation(
                    operator_name=metrics.operator_name,
                    strategy=OptimizationStrategy.ALGORITHM_REPLACEMENT,
                    reason=f"Success rate {metrics.success_rate:.2f} below threshold {self.low_success_threshold}",
                    details={"current_success_rate": metrics.success_rate, "failure_modes": metrics.failure_modes},
                )
            )

        # Low confidence -> prompt improvement
        if metrics.avg_confidence < self.low_confidence_threshold:
            recommendations.append(
                OptimizationRecommendation(
                    operator_name=metrics.operator_name,
                    strategy=OptimizationStrategy.PROMPT_IMPROVEMENT,
                    reason=f"Average confidence {metrics.avg_confidence:.2f} below threshold {self.low_confidence_threshold}",
                    details={"current_avg_confidence": metrics.avg_confidence},
                )
            )

        # High runtime -> parameter tuning
        if metrics.avg_runtime > self.high_runtime_threshold:
            recommendations.append(
                OptimizationRecommendation(
                    operator_name=metrics.operator_name,
                    strategy=OptimizationStrategy.PARAMETER_TUNING,
                    reason=f"Average runtime {metrics.avg_runtime:.2f}s exceeds threshold {self.high_runtime_threshold}s",
                    details={"current_avg_runtime": metrics.avg_runtime},
                )
            )

        return recommendations
