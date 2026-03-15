"""Graph store facade — stable read/write API above graph_store.py.

Provides a simplified interface for the most common graph operations,
delegating to the underlying GraphStore.
"""
from __future__ import annotations

from typing import Any

from research_engine.graph.graph_store import GraphStore, GraphNode, GraphEdge
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType


class Store:
    """Stable read/write facade over GraphStore.

    Usage::

        store = Store()
        node = store.add_node(NodeType.CLAIM, {"text": "Earth is round"})
        store.add_edge(EdgeType.SUPPORTS, source_id, target_id)
    """

    def __init__(self, graph: GraphStore | None = None) -> None:
        self._graph = graph or GraphStore()

    @property
    def graph(self) -> GraphStore:
        """Access the underlying graph store."""
        return self._graph

    def add_node(
        self,
        node_type: NodeType,
        content: dict[str, Any],
        **kwargs: Any,
    ) -> GraphNode:
        return self._graph.add_node(node_type, content, **kwargs)

    def get_node(self, node_id: str) -> GraphNode:
        return self._graph.get_node(node_id)

    def update_node(
        self,
        node_id: str,
        content: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        return self._graph.update_node(node_id, content, metadata)

    def remove_node(self, node_id: str) -> None:
        self._graph.remove_node(node_id)

    def query_nodes(self, **kwargs: Any) -> list[GraphNode]:
        return self._graph.query_nodes(**kwargs)

    def add_edge(
        self,
        edge_type: EdgeType,
        source_id: str,
        target_id: str,
        **kwargs: Any,
    ) -> GraphEdge:
        return self._graph.add_edge(edge_type, source_id, target_id, **kwargs)

    def get_edge(self, edge_id: str) -> GraphEdge:
        return self._graph.get_edge(edge_id)

    def remove_edge(self, edge_id: str) -> None:
        self._graph.remove_edge(edge_id)

    def query_edges(self, **kwargs: Any) -> list[GraphEdge]:
        return self._graph.query_edges(**kwargs)

    def neighbors(self, node_id: str, **kwargs: Any) -> list[GraphNode]:
        return self._graph.neighbors(node_id, **kwargs)

    @property
    def node_count(self) -> int:
        return self._graph.node_count

    @property
    def edge_count(self) -> int:
        return self._graph.edge_count
