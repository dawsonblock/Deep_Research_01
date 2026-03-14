"""Agent router — routes typed tasks to the correct specialist agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.agents.core.agent_base import AgentBase
from research_engine.agents.core.agent_registry import AgentRegistry
from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    validate_request,
)


@dataclass
class RoutingResult:
    """Result of routing a task to an agent."""
    routed: bool
    agent_id: str = ""
    response: AgentResponse | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "routed": self.routed,
            "agent_id": self.agent_id,
            "error": self.error,
            "response": self.response.to_dict() if self.response else None,
        }


class AgentRouter:
    """Routes typed tasks to specialist agents."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._routing_history: list[RoutingResult] = []

    def route(self, request: AgentRequest) -> RoutingResult:
        """Route a request to the best matching agent.

        Selection priority:
        1. Find agents that can handle the task_type
        2. If multiple, pick first match (future: use scoring)
        3. Execute the request on the chosen agent
        """
        # Validate request
        valid, reason = validate_request(request)
        if not valid:
            result = RoutingResult(routed=False, error=f"Invalid request: {reason}")
            self._routing_history.append(result)
            return result

        # Find capable agents
        agents = self.registry.find_for_task(request.task_type)
        if not agents:
            result = RoutingResult(
                routed=False,
                error=f"No agent found for task type: {request.task_type}",
            )
            self._routing_history.append(result)
            return result

        # Select agent (first match for now)
        agent = agents[0]

        # Execute
        try:
            response = agent.execute_request(request)
            result = RoutingResult(
                routed=True,
                agent_id=agent.agent_id,
                response=response,
            )
        except Exception as exc:
            result = RoutingResult(
                routed=False,
                agent_id=agent.agent_id,
                error=f"{type(exc).__name__}: {exc}",
            )

        self._routing_history.append(result)
        return result

    def route_to_specific(self, agent_id: str, request: AgentRequest) -> RoutingResult:
        """Route a request to a specific agent by ID."""
        agent = self.registry.get(agent_id)
        if agent is None:
            result = RoutingResult(routed=False, error=f"Agent not found: {agent_id}")
            self._routing_history.append(result)
            return result

        try:
            response = agent.execute_request(request)
            result = RoutingResult(routed=True, agent_id=agent_id, response=response)
        except Exception as exc:
            result = RoutingResult(
                routed=False,
                agent_id=agent_id,
                error=f"{type(exc).__name__}: {exc}",
            )

        self._routing_history.append(result)
        return result

    @property
    def routing_history(self) -> list[RoutingResult]:
        return list(self._routing_history)
