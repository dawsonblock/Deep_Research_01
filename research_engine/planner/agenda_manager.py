"""Agenda manager — public entrypoint for the planner pipeline.

This is the module that backend/services/planner.py should delegate to.
It orchestrates: proposer → critic → selector.
"""
from __future__ import annotations

from typing import Any

from research_engine.planner.research_planner import PlannerState
from research_engine.planner.proposer import Proposer
from research_engine.planner.critic import Critic
from research_engine.planner.selector import Selector
from research_engine.planner.orchestrator import PlanProposal
from research_engine.planner.strategy_memory import StrategyMemory


class AgendaManager:
    """Top-level planner API.

    Usage::

        manager = AgendaManager()
        result = manager.plan(state)
        if result:
            print(result.actions)
    """

    def __init__(
        self,
        memory: StrategyMemory | None = None,
        max_proposals: int = 3,
    ) -> None:
        self._memory = memory or StrategyMemory()
        self._proposer = Proposer()
        self._critic = Critic(memory=self._memory)
        self._selector = Selector()
        self._max_proposals = max_proposals

    def plan(
        self, state: PlannerState, context: str = "default"
    ) -> PlanProposal | None:
        """Run the full proposer → critic → selector pipeline.

        Args:
            state: Current planner state.
            context: Context label for strategy memory lookups.

        Returns:
            The selected PlanProposal, or None.
        """
        proposals = self._proposer.propose(state, max_proposals=self._max_proposals)
        if not proposals:
            return None
        scores = self._critic.score_all(proposals, context)
        return self._selector.select(proposals, scores)

    def record_outcome(
        self, action: str, context: str, success: bool
    ) -> None:
        """Record the outcome of an executed plan for strategy memory."""
        self._memory.record_outcome(action, context, success)

    @property
    def strategy_memory(self) -> StrategyMemory:
        return self._memory
