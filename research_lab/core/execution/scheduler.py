"""Scheduler for executing ready tasks from the task graph."""
from __future__ import annotations

from research_lab.core.execution.task_graph import TaskGraph
from research_lab.core.execution.execution_node import ExecutionNode, NodeStatus


class Scheduler:
    """Selects and dispatches ready nodes from the task graph."""

    def __init__(self, graph: TaskGraph) -> None:
        self.graph = graph

    def next_batch(self) -> list[ExecutionNode]:
        """Return the next batch of ready-to-execute nodes."""
        ready = self.graph.ready_nodes()
        for node in ready:
            node.status = NodeStatus.READY
        return ready

    def complete(self, node_id: str, result: dict | None = None) -> None:
        self.graph.mark_completed(node_id, result)

    def fail(self, node_id: str, error: str = "") -> None:
        self.graph.mark_failed(node_id, error)

    def is_done(self) -> bool:
        return self.graph.is_complete()
