"""Agent protocol — defines allowed and forbidden agent interactions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestType(str, Enum):
    """Types of requests agents can make."""
    TASK_PROPOSAL = "task_proposal"
    ARTIFACT_PROPOSAL = "artifact_proposal"
    EXECUTION_REQUEST = "execution_request"
    CRITIQUE_REQUEST = "critique_request"


class ForbiddenAction(str, Enum):
    """Actions that agents must never perform directly."""
    DIRECT_GRAPH_MUTATION = "direct_graph_mutation"
    DIRECT_CONFIDENCE_UPDATE = "direct_confidence_update"
    BYPASS_EXECUTOR = "bypass_executor"


@dataclass
class AgentRequest:
    """A typed request from an agent."""
    request_type: RequestType
    source_agent: str
    task_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_type": self.request_type.value,
            "source_agent": self.source_agent,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class AgentResponse:
    """Response from an agent's work."""
    source_agent: str
    task_type: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_agent": self.source_agent,
            "task_type": self.task_type,
            "success": self.success,
            "result": self.result,
            "errors": list(self.errors),
            "metadata": self.metadata,
        }


def validate_request(request: AgentRequest) -> tuple[bool, str]:
    """Validate that an agent request conforms to the protocol.

    Returns (is_valid, reason).
    """
    if not request.source_agent:
        return False, "source_agent is required"
    if not request.task_type:
        return False, "task_type is required"
    if request.request_type not in RequestType:
        return False, f"invalid request_type: {request.request_type}"
    return True, ""


def check_forbidden(action: str) -> bool:
    """Check if an action is forbidden by the protocol.

    Returns True if the action is forbidden.
    """
    forbidden_patterns = {
        "graph.add_node",
        "graph.update_node",
        "graph.remove_node",
        "belief_update.apply",
        "belief_update.update_claim_confidence",
        "artifact_store.create",
        "store.add_node",
        "store.add_edge",
    }
    return any(pattern in action for pattern in forbidden_patterns)
