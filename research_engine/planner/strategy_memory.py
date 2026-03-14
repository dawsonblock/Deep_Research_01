"""Persistent memory for planner strategy effectiveness."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class StrategyRecord:
    """Records the outcome of a strategy applied in a context."""
    action: str
    context: str
    total_uses: int = 0
    successes: int = 0
    success_rate: float = 0.0

    def record(self, success: bool) -> None:
        self.total_uses += 1
        if success:
            self.successes += 1
        self.success_rate = self.successes / self.total_uses

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "context": self.context,
            "total_uses": self.total_uses,
            "successes": self.successes,
            "success_rate": self.success_rate,
        }


class StrategyMemory:
    """Stores historical strategy performance for planner bias."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StrategyRecord] = {}

    def record_outcome(self, action: str, context: str, success: bool) -> StrategyRecord:
        key = (action, context)
        if key not in self._records:
            self._records[key] = StrategyRecord(action=action, context=context)
        self._records[key].record(success)
        return self._records[key]

    def get_record(self, action: str, context: str) -> StrategyRecord | None:
        return self._records.get((action, context))

    def best_action_for_context(self, context: str, min_uses: int = 1) -> str | None:
        """Return the action with the highest success rate for a given context."""
        candidates = [
            r for r in self._records.values()
            if r.context == context and r.total_uses >= min_uses
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.success_rate).action

    def all_records(self) -> list[StrategyRecord]:
        return list(self._records.values())
