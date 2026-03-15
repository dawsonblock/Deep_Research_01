"""Feedback engine — closes the experiment feedback loop.

After experiment artifact validation:
    1. Evaluate the result
    2. Update belief state
    3. Schedule follow-up or contradiction resolution
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.experiments.experiment_spec import ExperimentResult
from research_engine.experiments.result_evaluator import ResultEvaluator


@dataclass
class FeedbackAction:
    """An action recommended by the feedback engine."""
    action_type: str = ""
    target_id: str = ""
    rationale: str = ""
    priority: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_id": self.target_id,
            "rationale": self.rationale,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class FeedbackReport:
    """Result of running the feedback engine on an experiment result."""
    verdict: str = ""
    confidence_delta: float = 0.0
    actions: list[FeedbackAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence_delta": self.confidence_delta,
            "actions": [a.to_dict() for a in self.actions],
        }


class FeedbackEngine:
    """Processes experiment results and generates follow-up actions.

    Workflow:
        1. Evaluate the experiment result
        2. Determine if beliefs should be updated
        3. Generate follow-up actions (more experiments, contradiction resolution, etc.)
    """

    def __init__(self, evaluator: ResultEvaluator | None = None) -> None:
        self._evaluator = evaluator or ResultEvaluator()

    def process(self, result: ExperimentResult) -> FeedbackReport:
        """Process an experiment result and generate feedback.

        Args:
            result: The experiment result to evaluate.

        Returns:
            FeedbackReport with verdict and recommended actions.
        """
        evaluation = self._evaluator.evaluate(result)
        verdict = evaluation.get("verdict", "inconclusive")
        actions: list[FeedbackAction] = []

        if verdict == "supports":
            actions.append(FeedbackAction(
                action_type="update_belief",
                target_id=result.spec_id,
                rationale="Experiment supports hypothesis — increase confidence",
                priority=2,
            ))
        elif verdict == "weak_support":
            actions.append(FeedbackAction(
                action_type="design_followup_experiment",
                target_id=result.spec_id,
                rationale="Weak support — additional evidence needed",
                priority=3,
            ))
        elif verdict == "inconclusive":
            actions.append(FeedbackAction(
                action_type="investigate_failure",
                target_id=result.spec_id,
                rationale=f"Experiment inconclusive: {evaluation.get('reason', '')}",
                priority=4,
            ))

        # If confidence is very low, consider contradiction resolution
        if result.confidence < 0.3 and result.success:
            actions.append(FeedbackAction(
                action_type="resolve_contradiction",
                target_id=result.spec_id,
                rationale="Very low confidence — may indicate contradiction",
                priority=5,
            ))

        return FeedbackReport(
            verdict=verdict,
            confidence_delta=result.confidence - 0.5,
            actions=actions,
        )
