"""Agent base class — shared interface for all specialist agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from research_engine.agents.core.agent_protocol import (
    AgentRequest,
    AgentResponse,
    RequestType,
)


class AgentBase(ABC):
    """Base class for all specialist agents.

    Every agent must declare what task types it can handle,
    propose work via typed requests, and summarize outcomes.
    Agents must NOT mutate the graph directly.
    """

    def __init__(self, agent_id: str, agent_type: str) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type

    @abstractmethod
    def can_handle(self, task_type: str) -> bool:
        """Return True if this agent can handle the given task type."""
        ...

    @abstractmethod
    def propose(self, task: dict[str, Any]) -> AgentRequest:
        """Propose work to be done for a task.

        Returns an AgentRequest that will be routed through the executor.
        """
        ...

    @abstractmethod
    def execute_request(self, request: AgentRequest) -> AgentResponse:
        """Execute or delegate a request.

        Agents process the request and return results, but must NOT
        mutate the graph directly. Results flow through the verified executor.
        """
        ...

    def summarize_outcome(self, response: AgentResponse) -> dict[str, Any]:
        """Summarize the outcome of an agent's work."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "task_type": response.task_type,
            "success": response.success,
            "errors": response.errors,
        }

    def create_request(
        self,
        request_type: RequestType,
        task_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> AgentRequest:
        """Helper to create a properly formed request."""
        return AgentRequest(
            request_type=request_type,
            source_agent=self.agent_id,
            task_type=task_type,
            payload=payload or {},
            priority=priority,
        )
