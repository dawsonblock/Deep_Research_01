"""Graph traversal utilities."""
from __future__ import annotations
from collections import deque

from research_lab.knowledge.graph.graph_store import GraphStore, GraphNode


class GraphTraversal:
    """BFS and DFS traversal over the knowledge graph."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def bfs(self, start_id: str, max_depth: int = 10) -> list[GraphNode]:
        """Breadth-first traversal from a start node."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        result: list[GraphNode] = []

        while queue:
            node_id, depth = queue.popleft()
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            node = self.store.get_node(node_id)
            if node:
                result.append(node)
                for neighbor in self.store.neighbors(node_id, direction="outgoing"):
                    if neighbor.node_id not in visited:
                        queue.append((neighbor.node_id, depth + 1))
        return result

    def dfs(self, start_id: str, max_depth: int = 10) -> list[GraphNode]:
        """Depth-first traversal from a start node."""
        visited: set[str] = set()
        result: list[GraphNode] = []

        def visit(node_id: str, depth: int) -> None:
            if node_id in visited or depth > max_depth:
                return
            visited.add(node_id)
            node = self.store.get_node(node_id)
            if node:
                result.append(node)
                for neighbor in self.store.neighbors(node_id, direction="outgoing"):
                    visit(neighbor.node_id, depth + 1)

        visit(start_id, 0)
        return result

    def find_path(self, start_id: str, end_id: str) -> list[str] | None:
        """Find a path between two nodes using BFS."""
        visited: set[str] = set()
        queue: deque[list[str]] = deque([[start_id]])

        while queue:
            path = queue.popleft()
            node_id = path[-1]
            if node_id == end_id:
                return path
            if node_id in visited:
                continue
            visited.add(node_id)
            for neighbor in self.store.neighbors(node_id, direction="outgoing"):
                if neighbor.node_id not in visited:
                    queue.append(path + [neighbor.node_id])
        return None
