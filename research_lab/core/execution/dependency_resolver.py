"""Resolve execution order from task graph dependencies."""
from __future__ import annotations

from research_lab.core.execution.execution_node import ExecutionNode


class CycleError(Exception):
    """Raised when a cycle is detected in the task graph."""


class DependencyResolver:
    """Topological sort of execution nodes."""

    def resolve(self, nodes: list[ExecutionNode]) -> list[ExecutionNode]:
        """Return nodes in dependency-respecting execution order."""
        node_map = {n.node_id: n for n in nodes}
        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[ExecutionNode] = []

        def visit(node_id: str) -> None:
            if node_id in in_stack:
                raise CycleError(f"Cycle detected involving {node_id}")
            if node_id in visited:
                return
            in_stack.add(node_id)
            node = node_map.get(node_id)
            if node:
                for dep in node.dependencies:
                    visit(dep)
            in_stack.discard(node_id)
            visited.add(node_id)
            if node:
                order.append(node)

        for n in nodes:
            visit(n.node_id)
        return order
