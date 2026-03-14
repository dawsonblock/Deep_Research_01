"""Agent registry — stores available agents and their capabilities."""
from __future__ import annotations

from typing import Any

from research_engine.agents.core.agent_base import AgentBase


class AgentRegistry:
    """Registry of available specialist agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentBase] = {}

    def register(self, agent: AgentBase) -> None:
        """Register an agent and index its capabilities."""
        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentBase | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def find_for_task(self, task_type: str) -> list[AgentBase]:
        """Find all agents that can handle a given task type."""
        return [
            agent for agent in self._agents.values()
            if agent.can_handle(task_type)
        ]

    def list_agents(self) -> list[AgentBase]:
        """List all registered agents."""
        return list(self._agents.values())

    def list_agent_ids(self) -> list[str]:
        """List all registered agent IDs."""
        return sorted(self._agents.keys())
