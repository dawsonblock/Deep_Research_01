"""Belief update rules for the belief graph."""
from __future__ import annotations

from typing import Any

from research_lab.knowledge.belief.belief_graph import BeliefGraph
from research_lab.knowledge.graph.temporal.version_tracker import VersionTracker
from research_lab.knowledge.graph.temporal.temporal_graph import TemporalGraph


class BeliefUpdater:
    """Applies evidence-based updates to belief confidence.

    When a VersionTracker is provided, every update creates a revision
    node so that the full confidence history is preserved.
    """

    def __init__(
        self,
        graph: BeliefGraph,
        tracker: VersionTracker | None = None,
        temporal_graph: TemporalGraph | None = None,
    ) -> None:
        self.graph = graph
        self.tracker = tracker
        self.temporal_graph = temporal_graph

    def update_claim_confidence(
        self,
        claim_id: str,
        *,
        cause: str = "evidence_update",
        cause_id: str | None = None,
    ) -> dict[str, Any]:
        """Recalculate claim confidence from supporting/contradicting evidence.

        Returns a dict with old_confidence, new_confidence, and optionally
        the revision_id if temporal tracking is active.
        """
        try:
            node = self.graph.store.get_node(claim_id)
        except KeyError:
            return {"old_confidence": 0.0, "new_confidence": 0.0, "revision_id": None}

        old_confidence = node.metadata.get("confidence", 0.0)

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

        # Record revision if temporal tracking is available
        revision_id = None
        if self.tracker is not None:
            cause_desc = cause
            if cause_id:
                cause_desc = f"{cause}:{cause_id}"

            revision = self.tracker.create_revision(
                entity_type="claim",
                entity_id=claim_id,
                new_state={
                    "confidence": new_confidence,
                    "old_confidence": old_confidence,
                    "support": support,
                    "contradiction": contradiction,
                },
                cause=cause_desc,
                metadata={"cause_id": cause_id} if cause_id else {},
            )
            revision_id = revision.revision_id

            # Add version node + edges to temporal graph if available
            if self.temporal_graph is not None:
                self.temporal_graph.add_version_node(revision)

                # Link supersedes to previous revision
                if revision.previous_revision_id:
                    try:
                        self.temporal_graph.link_supersedes(
                            revision.revision_id, revision.previous_revision_id
                        )
                    except KeyError:
                        pass  # previous version node may not be in graph yet

                # Link revises to the original claim node
                try:
                    self.temporal_graph.link_revises(revision.revision_id, claim_id)
                except KeyError:
                    pass

                # Add causal edge if we know what strengthened/weakened it
                if cause_id:
                    from research_lab.knowledge.graph.edge_types import EdgeType
                    if new_confidence > old_confidence:
                        edge_type = EdgeType.STRENGTHENED_BY
                    elif new_confidence < old_confidence:
                        edge_type = EdgeType.WEAKENED_BY
                    else:
                        edge_type = None

                    if edge_type is not None:
                        try:
                            self.temporal_graph.link_causal(
                                edge_type,
                                source_id=revision.revision_id,
                                target_id=cause_id,
                            )
                        except (KeyError, ValueError):
                            pass

        # Update the node's latest confidence
        node.metadata["confidence"] = new_confidence
        self.graph.store.update_node(claim_id, metadata={"confidence": new_confidence})

        return {
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "revision_id": revision_id,
        }
