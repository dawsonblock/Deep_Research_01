"""Detects contradictions between claims in the knowledge graph."""
from __future__ import annotations
from dataclasses import dataclass, field

from research_engine.graph.graph_store import GraphStore, GraphNode
from research_engine.graph.node_types import NodeType
from research_engine.graph.edge_types import EdgeType


@dataclass
class Conflict:
    """A detected conflict between two claims."""
    claim_a_id: str
    claim_b_id: str
    conflict_type: str = "contradiction"
    severity: float = 0.0
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_a_id": self.claim_a_id,
            "claim_b_id": self.claim_b_id,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "details": self.details,
        }


class ConflictDetector:
    """Detects contradictions in the knowledge graph."""

    def _preview_content(self, content, max_len: int = 50) -> str:
        """Safely extract a short text preview from a node's content."""
        # Canonical GraphStore may store content as a dict, e.g. {"text": ...}.
        # Normalize to string before truncating to avoid TypeError on slicing.
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                value = text
            else:
                value = str(content)
        else:
            value = str(content)
        return value[:max_len]

    def detect_from_edges(self, store: GraphStore) -> list[Conflict]:
        """Find conflicts based on contradiction edges."""
        conflicts: list[Conflict] = []
        for edge in store.query_edges(edge_type=EdgeType.CONTRADICTS):
            try:
                src = store.get_node(edge.source_id)
                tgt = store.get_node(edge.target_id)
            except KeyError:
                # Skip edges that reference missing nodes instead of raising.
                continue
            if src and tgt:
                severity = edge.weight
                src_preview = self._preview_content(src.content)
                tgt_preview = self._preview_content(tgt.content)
                conflicts.append(Conflict(
                    claim_a_id=edge.source_id,
                    claim_b_id=edge.target_id,
                    severity=severity,
                    details=f"'{src_preview}' contradicts '{tgt_preview}'",
                ))
        return conflicts

    def detect_by_polarity(self, claims: list[dict]) -> list[Conflict]:
        """Find conflicts based on same subject + opposite polarity."""
        by_subject: dict[str, list[dict]] = {}
        for c in claims:
            subj = c.get("subject", "")
            if subj:
                by_subject.setdefault(subj, []).append(c)

        conflicts: list[Conflict] = []
        for subj, group in by_subject.items():
            positives = [c for c in group if c.get("polarity") == "positive"]
            negatives = [c for c in group if c.get("polarity") == "negative"]
            for p in positives:
                for n in negatives:
                    conflicts.append(Conflict(
                        claim_a_id=p.get("id", ""),
                        claim_b_id=n.get("id", ""),
                        conflict_type="polarity_contradiction",
                        severity=0.8,
                        details=f"Opposite polarity on subject '{subj}'",
                    ))
        return conflicts
