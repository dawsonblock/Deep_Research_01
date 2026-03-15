"""Proposer — generates multiple plan proposals for the planner pipeline.

Each proposal is a candidate action sequence that will be scored by the
critic and selected by the selector.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from research_engine.planner.research_planner import ResearchPlanner, PlannerState
from research_engine.planner.orchestrator import PlanProposal


class Proposer:
    """Generates candidate plans from the current state."""

    def __init__(self, planner: ResearchPlanner | None = None) -> None:
        self._planner = planner or ResearchPlanner()

    def propose(self, state: PlannerState, max_proposals: int = 3) -> list[PlanProposal]:
        """Generate up to max_proposals candidate plans.

        Currently generates one rule-based proposal. Future versions will
        explore alternative action sequences.
        """
        primary_action = self._planner.select_action(state)
        proposals = [
            PlanProposal(
                plan_id=uuid.uuid4().hex[:8],
                actions=[primary_action],
                rationale="Primary rule-based selection",
            )
        ]
        # Generate alternative proposals from the action list
        for action in ResearchPlanner.ACTIONS:
            if action != primary_action and len(proposals) < max_proposals:
                proposals.append(
                    PlanProposal(
                        plan_id=uuid.uuid4().hex[:8],
                        actions=[action],
                        rationale=f"Alternative action: {action}",
                        expected_gain=0.1,
                    )
                )
        return proposals[:max_proposals]
