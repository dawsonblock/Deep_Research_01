"""Experiment specification and schema."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class ExperimentSpec:
    """Specification for a research experiment."""
    spec_id: str = ""
    hypothesis: str = ""
    variables: dict = field(default_factory=dict)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.spec_id:
            self.spec_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "spec_id": self.spec_id,
            "hypothesis": self.hypothesis,
            "variables": dict(self.variables),
            "datasets": list(self.datasets),
            "metrics": list(self.metrics),
            "config": dict(self.config),
        }


@dataclass
class ExperimentResult:
    """Result of running an experiment."""
    spec_id: str = ""
    success: bool = False
    metrics: dict = field(default_factory=dict)
    confidence: float = 0.0
    error: str = ""
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "spec_id": self.spec_id,
            "success": self.success,
            "metrics": dict(self.metrics),
            "confidence": self.confidence,
            "error": self.error,
            "artifacts": list(self.artifacts),
        }
