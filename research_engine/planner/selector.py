"""Selector — picks the best scored plan from critic output."""
from __future__ import annotations

from research_engine.planner.orchestrator import PlanProposal
from research_engine.planner.critic import PlanScore


class Selector:
    """Picks the best plan proposal based on critic scores."""

    def select(
        self,
        proposals: list[PlanProposal],
        scores: list[PlanScore],
    ) -> PlanProposal | None:
        """Select the proposal with the highest composite score.

        Args:
            proposals: List of plan proposals.
            scores: Corresponding scores from the critic.

        Returns:
            The best proposal, or None if no proposals.
        """
        if not proposals or not scores:
            return None

        score_map = {s.plan_id: s for s in scores}
        best = max(proposals, key=lambda p: score_map.get(p.plan_id, PlanScore()).composite)
        return best
