"""Optimizes planner strategy selection based on historical performance."""
from __future__ import annotations

from research_engine.planner.strategy_memory import StrategyMemory


class StrategyOptimizer:
    """Uses strategy memory to bias planner toward successful actions."""

    def __init__(self, memory: StrategyMemory, exploration_rate: float = 0.1) -> None:
        self.memory = memory
        self.exploration_rate = exploration_rate

    def rank_actions(self, actions: list[str], context: str) -> list[tuple[str, float]]:
        """Rank actions by historical success rate in the given context."""
        scored: list[tuple[str, float]] = []
        for action in actions:
            record = self.memory.get_record(action, context)
            if record and record.total_uses > 0:
                scored.append((action, record.success_rate))
            else:
                # Unknown actions get exploration bonus
                scored.append((action, self.exploration_rate))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def select_action(self, actions: list[str], context: str) -> str | None:
        """Select the highest-ranked action for a context."""
        ranked = self.rank_actions(actions, context)
        if not ranked:
            return None
        return ranked[0][0]
