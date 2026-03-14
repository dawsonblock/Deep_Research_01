"""Quality metrics for system self-assessment."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class QualitySnapshot:
    """A snapshot of quality metrics at a point in time."""
    artifact_quality: float = 0.0
    reasoning_accuracy: float = 0.0
    experiment_reproducibility: float = 0.0
    planner_efficiency: float = 0.0

    @property
    def overall_score(self) -> float:
        scores = [
            self.artifact_quality,
            self.reasoning_accuracy,
            self.experiment_reproducibility,
            self.planner_efficiency,
        ]
        return sum(scores) / len(scores) if scores else 0.0

    def to_dict(self) -> dict:
        return {
            "artifact_quality": self.artifact_quality,
            "reasoning_accuracy": self.reasoning_accuracy,
            "experiment_reproducibility": self.experiment_reproducibility,
            "planner_efficiency": self.planner_efficiency,
            "overall_score": self.overall_score,
        }


class QualityMetricsTracker:
    """Tracks quality metrics over time."""

    def __init__(self) -> None:
        self._snapshots: list[QualitySnapshot] = []

    def record(self, snapshot: QualitySnapshot) -> None:
        self._snapshots.append(snapshot)

    def latest(self) -> QualitySnapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    def trend(self, n: int = 5) -> list[float]:
        """Return recent overall scores to show quality trend."""
        return [s.overall_score for s in self._snapshots[-n:]]

    def is_improving(self) -> bool:
        """Check if quality trend is positive."""
        recent = self.trend(3)
        if len(recent) < 2:
            return True
        return recent[-1] >= recent[0]

    def all_snapshots(self) -> list[QualitySnapshot]:
        return list(self._snapshots)
