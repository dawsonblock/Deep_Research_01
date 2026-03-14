"""Belief update rules for the belief graph."""
from __future__ import annotations

from research_lab.knowledge.belief.belief_graph import BeliefGraph


class BeliefUpdater:
    """Applies evidence-based updates to belief confidence."""

    def __init__(self, graph: BeliefGraph) -> None:
        self.graph = graph

    def update_claim_confidence(self, claim_id: str) -> float:
        """Recalculate claim confidence from supporting/contradicting evidence."""
        node = self.graph.store.get_node(claim_id)
        if not node:
            return 0.0

        support = 0.0
        contradiction = 0.0
        for edge in self.graph.store.query_edges():
            if edge.target_id == claim_id:
                w = edge.metadata.get("weight", 1.0)
                if edge.edge_type.value == "supports":
                    source = self.graph.store.get_node(edge.source_id)
                    if source:
                        support += source.metadata.get("confidence", 0.5) * w
                elif edge.edge_type.value == "contradicts":
                    source = self.graph.store.get_node(edge.source_id)
                    if source:
                        contradiction += source.metadata.get("confidence", 0.5) * w

        total = support + contradiction
        new_confidence = support / total if total > 0 else 0.5
        node.metadata["confidence"] = new_confidence
        self.graph.store.update_node(claim_id, metadata={"confidence": new_confidence})
        return new_confidence
