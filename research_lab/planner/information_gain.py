"""Information gain estimation for planner decisions."""
from __future__ import annotations


class InformationGainEstimator:
    """Estimates information gain of potential research actions."""

    def __init__(self) -> None:
        self._action_gains: dict[str, float] = {}

    def estimate(self, action: str, context: dict | None = None) -> float:
        """Return estimated information gain for an action."""
        return self._action_gains.get(action, 0.5)

    def update(self, action: str, observed_gain: float, alpha: float = 0.1) -> None:
        """Update gain estimate using exponential moving average."""
        current = self._action_gains.get(action, 0.5)
        self._action_gains[action] = current * (1 - alpha) + observed_gain * alpha

    def rank_actions(self, actions: list[str]) -> list[tuple[str, float]]:
        """Rank actions by estimated information gain."""
        ranked = [(a, self.estimate(a)) for a in actions]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
