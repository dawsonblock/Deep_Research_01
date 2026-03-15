"""Belief updater — applies evidence-based updates to belief confidence.

Ported from research_lab/knowledge/belief/belief_update.py to use
canonical research_engine modules.
"""
from __future__ import annotations

from typing import Any

from research_engine.beliefs.belief_model import Belief
from research_engine.beliefs.belief_store import BeliefStore
from research_engine.graph.graph_store import GraphStore
from research_engine.graph.edge_types import EdgeType
from research_engine.graph.temporal.version_tracker import VersionTracker


class BeliefUpdater:
    """Recalculates belief confidence from supporting/contradicting evidence.

    When a VersionTracker is provided, every update creates a revision
    so that the full confidence history is preserved.
    """

    def __init__(
        self,
        store: BeliefStore,
        graph: GraphStore,
        tracker: VersionTracker | None = None,
    ) -> None:
        self._store = store
        self._graph = graph
        self._tracker = tracker

    def update(
        self,
        claim_id: str,
        *,
        cause: str = "evidence_update",
        cause_id: str | None = None,
    ) -> dict[str, Any]:
        """Recalculate belief confidence from graph evidence.

        Returns dict with old_confidence, new_confidence, and optionally
        revision_id if temporal tracking is active.
        """
        belief = self._store.get_by_claim(claim_id)
        old_confidence = belief.confidence if belief else 0.5

        support = 0.0
        contradiction = 0.0
        for edge in self._graph.query_edges():
            if edge.target_id == claim_id:
                try:
                    source = self._graph.get_node(edge.source_id)
                except KeyError:
                    continue
                w = edge.metadata.get("weight", 1.0)
                if edge.edge_type == EdgeType.SUPPORTS:
                    support += source.metadata.get("confidence", 0.5) * w
                elif edge.edge_type == EdgeType.CONTRADICTS:
                    contradiction += source.metadata.get("confidence", 0.5) * w

        total = support + contradiction
        new_confidence = support / total if total > 0 else 0.5

        # Update or create the belief
        if belief:
            self._store.update_confidence(claim_id, new_confidence)
        else:
            belief = Belief(claim_id=claim_id, confidence=new_confidence)
            self._store.store(belief)

        # Record temporal revision
        revision_id = None
        if self._tracker is not None:
            cause_desc = f"{cause}:{cause_id}" if cause_id else cause
            revision = self._tracker.create_revision(
                entity_type="claim",
                entity_id=claim_id,
                new_state={
                    "confidence": new_confidence,
                    "old_confidence": old_confidence,
                    "support": support,
                    "contradiction": contradiction,
                },
                cause=cause_desc,
            )
            revision_id = revision.revision_id

        return {
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "revision_id": revision_id,
        }
