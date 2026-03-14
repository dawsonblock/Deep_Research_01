"""Directed acyclic graph of execution tasks."""
from __future__ import annotations

from research_lab.core.execution.execution_node import ExecutionNode, NodeStatus


class TaskGraph:
    """DAG of execution nodes with dependency tracking."""

    def __init__(self) -> None:
        self._nodes: dict[str, ExecutionNode] = {}

    def add_node(self, node: ExecutionNode) -> None:
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> ExecutionNode | None:
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)
        for n in self._nodes.values():
            if node_id in n.dependencies:
                n.dependencies.remove(node_id)

    def ready_nodes(self) -> list[ExecutionNode]:
        completed = {
            n.node_id for n in self._nodes.values() if n.status == NodeStatus.COMPLETED
        }
        return [
            n for n in self._nodes.values()
            if n.status == NodeStatus.PENDING and n.is_ready(completed)
        ]

    def all_nodes(self) -> list[ExecutionNode]:
        return list(self._nodes.values())

    def is_complete(self) -> bool:
        return all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.FAILED)
            for n in self._nodes.values()
        )

    def mark_completed(self, node_id: str, result: dict | None = None) -> None:
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.COMPLETED
            node.result = result

    def mark_failed(self, node_id: str, error: str = "") -> None:
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.FAILED
            node.error = error
