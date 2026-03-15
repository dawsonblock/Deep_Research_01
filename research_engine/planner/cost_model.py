"""Cost model — estimates computational cost of plan actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Default cost estimates by action type (arbitrary units)
_DEFAULT_COSTS: dict[str, float] = {
    "ingest_literature": 1.0,
    "extract_claims": 2.0,
    "search_evidence": 1.5,
    "detect_conflicts": 1.0,
    "generate_hypotheses": 2.5,
    "design_experiment": 3.0,
    "run_experiment": 5.0,
    "evaluate_results": 1.5,
}


@dataclass
class CostEstimate:
    """Cost estimate for a plan action."""
    action: str
    base_cost: float = 0.0
    multiplier: float = 1.0

    @property
    def total(self) -> float:
        return self.base_cost * self.multiplier

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "base_cost": self.base_cost,
            "multiplier": self.multiplier,
            "total": self.total,
        }


class CostModel:
    """Estimates the cost of executing plan actions."""

    def __init__(self, cost_table: dict[str, float] | None = None) -> None:
        self._costs = cost_table or dict(_DEFAULT_COSTS)

    def estimate(self, action: str, multiplier: float = 1.0) -> CostEstimate:
        base = self._costs.get(action, 1.0)
        return CostEstimate(action=action, base_cost=base, multiplier=multiplier)

    def total_cost(self, actions: list[str]) -> float:
        return sum(self.estimate(a).total for a in actions)

    def register_cost(self, action: str, cost: float) -> None:
        self._costs[action] = cost
