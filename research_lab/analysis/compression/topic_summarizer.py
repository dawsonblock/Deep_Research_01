"""Summarizes research topics from the knowledge graph."""
from __future__ import annotations

from research_lab.knowledge.graph.graph_store import GraphStore
from research_lab.knowledge.graph.node_types import NodeType


class TopicSummarizer:
    """Generates summaries of research topics from graph content."""

    def summarize_claims(self, store: GraphStore) -> dict:
        """Summarize all claims in the graph."""
        claims = store.query_nodes(node_type=NodeType.CLAIM)
        if not claims:
            return {"topic": "unknown", "claim_count": 0, "summary": "No claims found."}

        sorted_claims = sorted(
            claims,
            key=lambda n: n.metadata.get("confidence", 0),
            reverse=True,
        )
        top_claims = [c.content[:150] for c in sorted_claims[:5]]
        return {
            "claim_count": len(claims),
            "top_claims": top_claims,
            "avg_confidence": sum(c.metadata.get("confidence", 0) for c in claims) / len(claims),
        }

    def summarize_hypotheses(self, store: GraphStore) -> dict:
        """Summarize active hypotheses."""
        hypotheses = store.query_nodes(node_type=NodeType.HYPOTHESIS)
        return {
            "hypothesis_count": len(hypotheses),
            "hypotheses": [{"id": h.node_id, "content": h.content[:200]} for h in hypotheses],
        }
