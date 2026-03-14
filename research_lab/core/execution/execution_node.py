"""Execution node for the task graph."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class NodeStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionNode:
    """A node in the execution task graph."""
    node_id: str
    operator: str
    inputs: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: dict | None = None
    error: str | None = None

    def is_ready(self, completed_nodes: set[str]) -> bool:
        return all(dep in completed_nodes for dep in self.dependencies)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "operator": self.operator,
            "inputs": self.inputs,
            "dependencies": list(self.dependencies),
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }
