"""Generates research reports from system state."""
from __future__ import annotations
from dataclasses import dataclass, field

from research_lab.knowledge.graph.graph_store import GraphStore
from research_lab.knowledge.graph.node_types import NodeType
from research_lab.knowledge.graph.edge_types import EdgeType


@dataclass
class ResearchReport:
    """A generated research report."""
    topic: str = ""
    sections: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"topic": self.topic, "sections": dict(self.sections)}


class ReportGenerator:
    """Generates structured research reports from the knowledge graph."""

    def generate(self, store: GraphStore, topic: str = "") -> ResearchReport:
        """Generate a report from the current graph state."""
        claims = store.query_nodes(node_type=NodeType.CLAIM)
        hypotheses = store.query_nodes(node_type=NodeType.HYPOTHESIS)
        contradictions = store.query_edges(edge_type=EdgeType.CONTRADICTS)

        sections = {
            "topic_summary": topic or "General Research",
            "key_claims": [{"id": c.node_id, "content": c.content[:200]} for c in claims[:10]],
            "contradictions": [
                {"source": e.source_id, "target": e.target_id}
                for e in contradictions
            ],
            "open_hypotheses": [
                {"id": h.node_id, "content": h.content[:200]}
                for h in hypotheses
            ],
            "stats": {
                "total_claims": len(claims),
                "total_hypotheses": len(hypotheses),
                "total_contradictions": len(contradictions),
            },
        }
        return ResearchReport(topic=topic, sections=sections)
