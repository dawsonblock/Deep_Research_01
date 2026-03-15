"""Evaluates experiment results against hypotheses."""
from __future__ import annotations

from research_engine.experiments.experiment_spec import ExperimentResult


class ResultEvaluator:
    """Evaluates whether experiment results support a hypothesis."""

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self.confidence_threshold = confidence_threshold

    def evaluate(self, result: ExperimentResult) -> dict:
        """Evaluate a single experiment result."""
        if not result.success:
            return {
                "spec_id": result.spec_id,
                "verdict": "inconclusive",
                "reason": f"Experiment failed: {result.error}",
            }

        if result.confidence >= self.confidence_threshold:
            return {
                "spec_id": result.spec_id,
                "verdict": "supports",
                "reason": f"Confidence {result.confidence:.2f} above threshold",
            }
        else:
            return {
                "spec_id": result.spec_id,
                "verdict": "weak_support",
                "reason": f"Confidence {result.confidence:.2f} below threshold {self.confidence_threshold}",
            }
