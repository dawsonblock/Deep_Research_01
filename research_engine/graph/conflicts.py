"""Graph conflicts — conflict detection and resolution utilities.

Wraps conflict-related graph queries and provides helpers for
identifying contradictions in the knowledge graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.graph.graph_store import GraphStore, GraphNode, GraphEdge
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType


@dataclass
class ConflictPair:
    """Represents a detected conflict between two nodes."""
    node_a_id: str
    node_b_id: str
    edge_id: str
    conflict_type: str = "contradiction"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "edge_id": self.edge_id,
            "conflict_type": self.conflict_type,
            "metadata": self.metadata,
        }


class ConflictDetector:
    """Detects conflicts (contradictions) in the knowledge graph."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def detect(self) -> list[ConflictPair]:
        """Find all contradiction edges in the graph."""
        edges = self._store.query_edges(edge_type=EdgeType.CONTRADICTS)
        conflicts = []
        for edge in edges:
            conflicts.append(
                ConflictPair(
                    node_a_id=edge.source_id,
                    node_b_id=edge.target_id,
                    edge_id=edge.edge_id,
                )
            )
        return conflicts

    def conflicts_for_node(self, node_id: str) -> list[ConflictPair]:
        """Find all contradictions involving a specific node."""
        outgoing = self._store.query_edges(edge_type=EdgeType.CONTRADICTS, source_id=node_id)
        incoming = self._store.query_edges(edge_type=EdgeType.CONTRADICTS, target_id=node_id)
        conflicts = []
        for edge in outgoing:
            conflicts.append(
                ConflictPair(
                    node_a_id=edge.source_id,
                    node_b_id=edge.target_id,
                    edge_id=edge.edge_id,
                )
            )
        for edge in incoming:
            conflicts.append(
                ConflictPair(
                    node_a_id=edge.source_id,
                    node_b_id=edge.target_id,
                    edge_id=edge.edge_id,
                )
            )
        return conflicts
