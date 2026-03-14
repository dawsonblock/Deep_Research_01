"""Belief graph layer built on top of the graph store."""
from __future__ import annotations

from research_lab.knowledge.graph.graph_store import GraphStore, GraphNode, GraphEdge
from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType


class BeliefGraph:
    """High-level belief graph API backed by GraphStore."""

    def __init__(self, store: GraphStore | None = None) -> None:
        self.store = store or GraphStore()

    def add_claim(self, content: str, confidence: float = 0.0, **metadata: object) -> str:
        meta = dict(metadata)
        meta["confidence"] = confidence
        return self.store.add_node(NodeType.CLAIM, content, metadata=meta)

    def add_evidence(self, content: str, confidence: float = 0.0, **metadata: object) -> str:
        meta = dict(metadata)
        meta["confidence"] = confidence
        return self.store.add_node(NodeType.EVIDENCE, content, metadata=meta)

    def add_hypothesis(self, content: str, **metadata: object) -> str:
        return self.store.add_node(NodeType.HYPOTHESIS, content, metadata=dict(metadata))

    def link_supports(self, source_id: str, target_id: str, weight: float = 1.0) -> str:
        return self.store.add_edge(source_id, target_id, EdgeType.SUPPORTS, metadata={"weight": weight})

    def link_contradicts(self, source_id: str, target_id: str, weight: float = 1.0) -> str:
        return self.store.add_edge(source_id, target_id, EdgeType.CONTRADICTS, metadata={"weight": weight})

    def get_claims(self) -> list[GraphNode]:
        return self.store.query_nodes(node_type=NodeType.CLAIM)

    def get_hypotheses(self) -> list[GraphNode]:
        return self.store.query_nodes(node_type=NodeType.HYPOTHESIS)

    def get_evidence_for(self, node_id: str) -> list[GraphNode]:
        """Get all evidence nodes supporting or contradicting a node."""
        neighbors = self.store.neighbors(node_id, direction="incoming")
        return [n for n in neighbors if n.node_type == NodeType.EVIDENCE]

    def get_contradictions(self) -> list[GraphEdge]:
        return self.store.query_edges(edge_type=EdgeType.CONTRADICTS)
