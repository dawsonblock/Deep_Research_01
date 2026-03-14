"""Experiment agent for designing and tracking experiments."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class ExperimentDesign:
    """Design specification for an experiment."""
    experiment_id: str = ""
    hypothesis_id: str = ""
    variables: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    status: str = "designed"

    def __post_init__(self) -> None:
        if not self.experiment_id:
            self.experiment_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "variables": list(self.variables),
            "datasets": list(self.datasets),
            "metrics": list(self.metrics),
            "status": self.status,
        }


class ExperimentAgent:
    """Designs experiments to test hypotheses."""

    def design_experiment(
        self,
        hypothesis: str,
        hypothesis_id: str = "",
        variables: list[str] | None = None,
    ) -> ExperimentDesign:
        """Create an experiment design for a hypothesis."""
        return ExperimentDesign(
            hypothesis_id=hypothesis_id,
            variables=variables or ["independent_var", "dependent_var"],
            metrics=["accuracy", "confidence"],
            status="designed",
        )

    def evaluate_result(self, design: ExperimentDesign, result: dict) -> dict:
        """Evaluate experiment results against the design."""
        return {
            "experiment_id": design.experiment_id,
            "hypothesis_id": design.hypothesis_id,
            "success": result.get("success", False),
            "confidence": result.get("confidence", 0.0),
            "recommendation": "supports_hypothesis" if result.get("success") else "rejects_hypothesis",
        }
