"""Query utilities for the knowledge graph."""
from __future__ import annotations

from research_lab.knowledge.graph.graph_store import GraphStore, GraphNode, GraphEdge
from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType


class GraphQueries:
    """High-level queries over the knowledge graph."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def claims_with_conflicts(self) -> list[tuple[GraphNode, GraphNode]]:
        """Find pairs of claims linked by contradiction edges."""
        pairs: list[tuple[GraphNode, GraphNode]] = []
        for edge in self.store.query_edges(edge_type=EdgeType.CONTRADICTS):
            src = self.store.get_node(edge.source_id)
            tgt = self.store.get_node(edge.target_id)
            if src and tgt:
                pairs.append((src, tgt))
        return pairs

    def unsupported_hypotheses(self) -> list[GraphNode]:
        """Find hypotheses with no supporting evidence."""
        hypotheses = self.store.query_nodes(node_type=NodeType.HYPOTHESIS)
        unsupported = []
        for h in hypotheses:
            incoming = self.store.neighbors(h.node_id, direction="incoming")
            has_support = any(
                e.edge_type == EdgeType.SUPPORTS
                for e in self.store.query_edges()
                if e.target_id == h.node_id
            )
            if not has_support:
                unsupported.append(h)
        return unsupported

    def evidence_for_claim(self, claim_id: str) -> list[GraphNode]:
        return self.store.neighbors(claim_id, direction="incoming")
