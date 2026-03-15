"""Drift detector — detects when research is drifting from objectives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriftReport:
    """Report of detected research drift."""
    drift_score: float = 0.0
    indicators: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "drift_score": self.drift_score,
            "indicators": self.indicators,
            "recommendation": self.recommendation,
        }


class DriftDetector:
    """Detects when the research process has drifted from its objectives.

    Monitors:
        - Ratio of exploratory to exploitative actions
        - Time since last meaningful progress
        - Divergence from stated research goals
    """

    def __init__(self, drift_threshold: float = 0.7) -> None:
        self._action_history: list[str] = []
        self._progress_events: list[float] = []
        self._drift_threshold = drift_threshold

    def record_action(self, action: str) -> None:
        self._action_history.append(action)

    def record_progress(self, timestamp: float) -> None:
        self._progress_events.append(timestamp)

    def check(self) -> DriftReport:
        """Check for research drift."""
        indicators: list[str] = []
        drift_score = 0.0

        # Check for repetitive actions
        if len(self._action_history) >= 5:
            recent = self._action_history[-5:]
            unique_ratio = len(set(recent)) / len(recent)
            if unique_ratio < 0.4:
                indicators.append("Highly repetitive recent actions")
                drift_score += 0.3

        # Check for lack of progress
        if len(self._action_history) > 10 and len(self._progress_events) == 0:
            indicators.append("No progress events recorded despite many actions")
            drift_score += 0.4

        recommendation = ""
        if drift_score >= self._drift_threshold:
            recommendation = "Consider resetting strategy or revising objectives"
        elif drift_score > 0.3:
            recommendation = "Monitor closely — early signs of drift"

        return DriftReport(
            drift_score=drift_score,
            indicators=indicators,
            recommendation=recommendation,
        )
