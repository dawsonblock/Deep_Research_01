"""Planner orchestrator — short-term home for current backend planning logic.

Wraps the existing ResearchPlanner with a project-aware interface that
the backend PlannerService can delegate to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.planner.research_planner import ResearchPlanner, PlannerState


@dataclass
class PlanProposal:
    """A proposed plan with actions and metadata."""
    plan_id: str = ""
    actions: list[str] = field(default_factory=list)
    rationale: str = ""
    expected_gain: float = 0.0
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "actions": self.actions,
            "rationale": self.rationale,
            "expected_gain": self.expected_gain,
            "cost_estimate": self.cost_estimate,
            "metadata": self.metadata,
        }


class PlannerOrchestrator:
    """Orchestrates the planning pipeline: propose → score → select.

    Currently wraps ResearchPlanner for backward compatibility.
    Future iterations will use the full proposer → critic → selector pipeline.
    """

    def __init__(self, planner: ResearchPlanner | None = None) -> None:
        self._planner = planner or ResearchPlanner()

    def propose(self, state: PlannerState) -> list[PlanProposal]:
        """Generate one or more plan proposals from the current state."""
        action = self._planner.select_action(state)
        return [
            PlanProposal(
                plan_id="default",
                actions=[action],
                rationale=f"Selected by rule-based planner from state: {state.to_dict()}",
            )
        ]

    def select(self, proposals: list[PlanProposal]) -> PlanProposal | None:
        """Select the best proposal. Currently returns the first."""
        return proposals[0] if proposals else None

    def plan(self, state: PlannerState) -> PlanProposal | None:
        """Full pipeline: propose then select."""
        proposals = self.propose(state)
        return self.select(proposals)
