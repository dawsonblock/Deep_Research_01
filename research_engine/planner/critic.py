"""Critic — scores plan proposals along multiple dimensions.

Scoring dimensions:
    - expected_information_gain: How much new knowledge the plan would produce.
    - expected_cost: Estimated compute/API cost.
    - novelty: Whether this action has been tried recently.
    - redundancy: Overlap with recently completed work.
    - safety: Risk of destructive or irreversible side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.planner.orchestrator import PlanProposal
from research_engine.planner.strategy_memory import StrategyMemory


@dataclass
class PlanScore:
    """Multi-dimensional score for a plan proposal."""
    plan_id: str = ""
    information_gain: float = 0.0
    cost: float = 0.0
    novelty: float = 0.0
    redundancy: float = 0.0
    safety: float = 1.0

    @property
    def composite(self) -> float:
        """Weighted composite score. Higher is better."""
        return (
            self.information_gain * 3.0
            + self.novelty * 1.5
            + self.safety * 2.0
            - self.cost * 1.0
            - self.redundancy * 2.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "information_gain": self.information_gain,
            "cost": self.cost,
            "novelty": self.novelty,
            "redundancy": self.redundancy,
            "safety": self.safety,
            "composite": self.composite,
        }


class Critic:
    """Scores plan proposals for the selector."""

    def __init__(self, memory: StrategyMemory | None = None) -> None:
        self._memory = memory or StrategyMemory()

    def score(self, proposal: PlanProposal, context: str = "default") -> PlanScore:
        """Score a single plan proposal."""
        action = proposal.actions[0] if proposal.actions else ""
        record = self._memory.get_record(action, context)

        novelty = 1.0
        if record and record.total_uses > 0:
            novelty = max(0.0, 1.0 - (record.total_uses / 10.0))

        info_gain = proposal.expected_gain if proposal.expected_gain > 0 else 0.5

        return PlanScore(
            plan_id=proposal.plan_id,
            information_gain=info_gain,
            cost=proposal.cost_estimate,
            novelty=novelty,
            safety=1.0,
        )

    def score_all(
        self, proposals: list[PlanProposal], context: str = "default"
    ) -> list[PlanScore]:
        """Score all proposals and return sorted by composite score (descending)."""
        scores = [self.score(p, context) for p in proposals]
        scores.sort(key=lambda s: s.composite, reverse=True)
        return scores
