"""Reasoning monitor — tracks reasoning quality metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningMetrics:
    """Metrics for a single reasoning cycle."""
    cycle_id: str = ""
    actions_taken: int = 0
    artifacts_produced: int = 0
    beliefs_updated: int = 0
    contradictions_found: int = 0
    loop_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "actions_taken": self.actions_taken,
            "artifacts_produced": self.artifacts_produced,
            "beliefs_updated": self.beliefs_updated,
            "contradictions_found": self.contradictions_found,
            "loop_detected": self.loop_detected,
        }


class ReasoningMonitor:
    """Tracks reasoning quality over time."""

    def __init__(self) -> None:
        self._history: list[ReasoningMetrics] = []

    def record(self, metrics: ReasoningMetrics) -> None:
        self._history.append(metrics)

    @property
    def history(self) -> list[ReasoningMetrics]:
        return list(self._history)

    def average_artifacts_per_cycle(self) -> float:
        if not self._history:
            return 0.0
        return sum(m.artifacts_produced for m in self._history) / len(self._history)

    def loop_rate(self) -> float:
        if not self._history:
            return 0.0
        loops = sum(1 for m in self._history if m.loop_detected)
        return loops / len(self._history)
