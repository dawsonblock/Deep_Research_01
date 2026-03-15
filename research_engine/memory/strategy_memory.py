"""Strategy memory — records which strategies worked in which contexts.

Bridges the planner's StrategyMemory with long-term persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyEntry:
    """A recorded strategy outcome."""
    strategy: str = ""
    context: str = ""
    success: bool = False
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "context": self.context,
            "success": self.success,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class StrategyMemoryStore:
    """Persistent strategy memory for cross-session learning."""

    def __init__(self) -> None:
        self._entries: list[StrategyEntry] = []

    def record(self, entry: StrategyEntry) -> None:
        self._entries.append(entry)

    def successes_for(self, strategy: str) -> list[StrategyEntry]:
        return [e for e in self._entries if e.strategy == strategy and e.success]

    def failures_for(self, strategy: str) -> list[StrategyEntry]:
        return [e for e in self._entries if e.strategy == strategy and not e.success]

    def success_rate(self, strategy: str) -> float:
        relevant = [e for e in self._entries if e.strategy == strategy]
        if not relevant:
            return 0.0
        return sum(1 for e in relevant if e.success) / len(relevant)

    @property
    def all_entries(self) -> list[StrategyEntry]:
        return list(self._entries)
