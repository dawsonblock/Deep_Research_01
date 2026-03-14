"""Planner agent for research coordination."""
from __future__ import annotations

from research_lab.planner.research_planner import ResearchPlanner, PlannerState


class PlannerAgent:
    """Agent wrapper around the research planner."""

    def __init__(self) -> None:
        self.planner = ResearchPlanner()

    def decide_next_action(
        self,
        open_hypotheses: int = 0,
        unresolved_conflicts: int = 0,
        untested_claims: int = 0,
        evidence_gaps: int = 0,
        pending_experiments: int = 0,
    ) -> str:
        """Decide the next research action based on current state."""
        state = PlannerState(
            open_hypotheses=open_hypotheses,
            unresolved_conflicts=unresolved_conflicts,
            untested_claims=untested_claims,
            evidence_gaps=evidence_gaps,
            pending_experiments=pending_experiments,
        )
        return self.planner.select_action(state)
